from interfaz4.estado import EstadoEnvios
from interfaz4.modelos import RegistroHito, Visita
from interfaz4.planificador import planificar
from tests.conftest import local

HITOS = [24, 12]


def visita(**kw):
    datos = dict(id="v1", apiario="produccion_miel", fecha="2026-10-10", desde="09:00", hasta="13:00")
    datos.update(kw)
    return Visita(**datos)


def estado(tmp_path, **hitos):
    e = EstadoEnvios(tmp_path / "envios.json")
    for clave, registro in hitos.items():
        e.actualizar("v1", int(clave.removeprefix("h")), registro)
    return e


def test_antes_de_las_24_h_no_hay_nada(tmp_path):
    plan = planificar([visita()], estado(tmp_path), HITOS, local("2026-10-09T08:59"))
    assert plan.acciones == [] and plan.marcas == []


def test_hito_24_vencido(tmp_path):
    plan = planificar([visita()], estado(tmp_path), HITOS, local("2026-10-09T09:17"))
    [a] = plan.acciones
    assert (a.hito, a.tipo, a.canales) == (24, "enviar", ["correo"])


def test_cron_demorado_igual_envia(tmp_path):
    plan = planificar([visita()], estado(tmp_path), HITOS, local("2026-10-09T14:40"))
    assert [(a.hito, a.tipo) for a in plan.acciones] == [(24, "enviar")]


def test_visita_cargada_10_h_antes_solo_12_y_24_omitido(tmp_path):
    plan = planificar([visita()], estado(tmp_path), HITOS, local("2026-10-09T23:00"))
    assert [(a.hito, a.tipo) for a in plan.acciones] == [(12, "enviar")]
    assert plan.marcas == [("v1", 24, "omitido")]


def test_despues_del_inicio_no_se_envia_y_se_marca_vencido(tmp_path):
    e = estado(tmp_path, h24=RegistroHito(estado="enviado"))
    plan = planificar([visita()], e, HITOS, local("2026-10-10T09:00"))
    assert plan.acciones == []
    assert plan.marcas == [("v1", 12, "vencido_sin_envio")]


def test_24_enviado_y_luego_12(tmp_path):
    e = estado(tmp_path, h24=RegistroHito(estado="enviado", canales={"correo": "ok"}))
    assert planificar([visita()], e, HITOS, local("2026-10-09T20:59")).acciones == []
    [a] = planificar([visita()], e, HITOS, local("2026-10-09T21:17")).acciones
    assert (a.hito, a.tipo) == (12, "enviar")


def test_reintento_solo_del_canal_fallido(tmp_path):
    reg = RegistroHito(estado="parcial", canales={"correo": "ok", "google_chat": "error: HTTP 500"})
    e = estado(tmp_path, h24=reg)
    [a] = planificar([visita(canales=["correo", "google_chat"])], e, HITOS, local("2026-10-09T10:17")).acciones
    assert (a.hito, a.tipo, a.canales) == (24, "reintentar", ["google_chat"])


def test_parcial_viejo_no_se_reintenta_cuando_vence_el_siguiente(tmp_path):
    e = estado(tmp_path, h24=RegistroHito(estado="error", canales={"correo": "error: SMTP"}))
    plan = planificar([visita()], e, HITOS, local("2026-10-09T21:17"))
    assert [(a.hito, a.tipo) for a in plan.acciones] == [(12, "enviar")]
    assert plan.marcas == []  # el 24 queda como estaba (error), no se pisa


def test_canceladas_e_idempotencia(tmp_path):
    assert planificar([visita(estado="cancelada")], estado(tmp_path), HITOS, local("2026-10-09T23:00")).acciones == []
    e = estado(tmp_path, h24=RegistroHito(estado="omitido"), h12=RegistroHito(estado="enviado"))
    assert planificar([visita()], e, HITOS, local("2026-10-09T23:30")).acciones == []
