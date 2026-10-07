from interfaz4.estado import EstadoEnvios
from interfaz4.modelos import RegistroHito, Visita
from interfaz4.planificador import planificar, proximo_momento
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


def test_proximo_es_el_hito_pendiente_siguiente(tmp_path):
    assert proximo_momento([visita()], estado(tmp_path), HITOS, local("2026-10-07T01:39")) == local("2026-10-09T09:00")
    e = estado(tmp_path, h24=RegistroHito(estado="enviado", canales={"correo": "ok"}))
    assert proximo_momento([visita()], e, HITOS, local("2026-10-09T09:03")) == local("2026-10-09T21:00")


def test_proximo_toma_la_visita_mas_cercana(tmp_path):
    visitas = [visita(), visita(id="v2", fecha="2026-10-09", desde="15:30", hasta="18:00")]
    assert proximo_momento(visitas, estado(tmp_path), HITOS, local("2026-10-08T10:00")) == local("2026-10-08T15:30")


def test_lo_vencido_no_se_reprograma(tmp_path):
    # Si la ejecución de `ahora` no pudo resolver un hito vencido, no se
    # vuelve a programar enseguida (evita ejecuciones en cadena).
    assert proximo_momento([visita()], estado(tmp_path), HITOS, local("2026-10-09T09:00")) == local("2026-10-09T21:00")
    e = estado(tmp_path, h24=RegistroHito(estado="enviado"), h12=RegistroHito(estado="enviado"))
    assert proximo_momento([visita()], e, HITOS, local("2026-10-09T21:05")) is None


def test_reintento_una_hora_despues_si_fallo(tmp_path):
    e = estado(tmp_path, h24=RegistroHito(estado="error", canales={"correo": "error: SMTP"}))
    assert proximo_momento([visita()], e, HITOS, local("2026-10-09T09:03")) == local("2026-10-09T10:03")
    e = estado(tmp_path, h24=RegistroHito(estado="parcial"))
    # Si el próximo hito vence antes que el reintento, va primero el hito.
    assert proximo_momento([visita()], e, HITOS, local("2026-10-09T20:30")) == local("2026-10-09T21:00")


def test_sin_reintento_si_la_visita_ya_habra_empezado(tmp_path):
    e = estado(tmp_path, h24=RegistroHito(estado="omitido"), h12=RegistroHito(estado="error"))
    assert proximo_momento([visita()], e, HITOS, local("2026-10-10T08:10")) is None
    assert proximo_momento([visita()], e, HITOS, local("2026-10-10T07:59")) == local("2026-10-10T08:59")


def test_sin_proximo_para_canceladas_o_pasadas(tmp_path):
    assert proximo_momento([visita(estado="cancelada")], estado(tmp_path), HITOS, local("2026-10-07T00:00")) is None
    assert proximo_momento([visita()], estado(tmp_path), HITOS, local("2026-10-10T09:00")) is None
    assert proximo_momento([], estado(tmp_path), HITOS, local("2026-10-07T00:00")) is None
