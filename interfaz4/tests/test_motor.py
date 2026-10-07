"""Ciclo de vida completo con reloj controlado (--ahora), datos offline y
envío real a un servidor SMTP local."""

import json
from datetime import UTC, datetime

import pytest
from typer.testing import CliRunner

from interfaz4.config import cargar_config
from interfaz4.estado import EstadoEnvios
from interfaz4.motor import Motor
from interfaz4.notificar import ErrorEnvio
from interfaz4.visitas.archivo_yaml import RepositorioYAML
from interfaz4.visitas.base import registrar_visita
from tests.conftest import local
from tests.datos_prueba import recolector_offline


class CorreoFalso:
    def __init__(self, fallar=False):
        self.enviados = []
        self.fallar = fallar

    def enviar(self, asunto, html, texto, destinatarios):
        if self.fallar:
            raise ErrorEnvio("correo sin configurar: faltan los secretos SMTP_USUARIO y/o SMTP_CLAVE_APP")
        self.enviados.append((asunto, destinatarios, texto))


class ChatFalso:
    def __init__(self, fallar=False):
        self.enviados = []
        self.fallar = fallar

    def enviar(self, mensajes, hilo=None):
        if self.fallar:
            raise ErrorEnvio("Google Chat respondió HTTP 500")
        self.enviados.append((hilo, mensajes))


def nueva_visita(config, **kw):
    datos = dict(apiario="produccion_miel", fecha="2026-10-04", desde="09:00", hasta="13:00", responsable="Eduardo Mendoza", ahora=local("2026-10-01T10:00"))
    datos.update(kw)
    return registrar_visita(config, RepositorioYAML(config.rutas.visitas_yaml), **datos)


def motor(config, tmp_path, correo=None, chat=None, fabricas=None):
    fabricas = fabricas if fabricas is not None else []

    def fabrica():
        fabricas.append(1)
        return recolector_offline(tmp_path, ahora=datetime(2026, 10, 4, 0, 17, tzinfo=UTC), alertas=[])

    return Motor(config, recolector_factory=fabrica, correo=correo or CorreoFalso(), chat=chat or ChatFalso())


def test_ciclo_24_12_con_idempotencia(config, tmp_path):
    v = nueva_visita(config)
    correo, fabricas = CorreoFalso(), []
    m = motor(config, tmp_path, correo=correo, fabricas=fabricas)

    r = m.ejecutar(local("2026-10-03T08:59"))
    assert r.acciones == []  # el hito vence a las 09:00
    assert r.proximo == local("2026-10-03T09:00")  # la espera se programa para esa hora
    assert "Próximo envío: sábado 03/10/2026 09:00" in r.resumen()
    r = m.ejecutar(local("2026-10-03T09:17"))
    assert [(a.hito, a.estado) for a in r.acciones] == [(24, "enviado")]
    assert r.proximo == local("2026-10-03T21:00")
    asunto, destinatarios, texto = correo.enviados[-1]
    assert asunto == "🐝 Visita Apiario de producción melífera 04/10 09:00–13:00 · informe 24 h"
    assert destinatarios == ["apicultor@example.com"]
    assert "Próximo informe: ~21:00 del sábado" in texto

    # Dos ejecuciones seguidas no duplican envíos y no consultan fuentes.
    assert motor(config, tmp_path, correo=correo, fabricas=fabricas).ejecutar(local("2026-10-03T10:17")).acciones == []
    assert len(correo.enviados) == 1 and len(fabricas) == 1

    r = motor(config, tmp_path, correo=correo).ejecutar(local("2026-10-03T21:17"))
    assert [(a.hito, a.estado) for a in r.acciones] == [(12, "enviado")]
    assert "CAMBIOS RESPECTO AL INFORME DE 24 H" in correo.enviados[-1][2]

    r = motor(config, tmp_path, correo=correo).ejecutar(local("2026-10-04T10:00"))
    assert r.acciones == [] and r.proximo is None
    assert "No quedan envíos pendientes." in r.resumen()
    estado = json.loads(config.rutas.envios_json.read_text())
    assert estado[v.id]["24"]["estado"] == "enviado"
    assert estado[v.id]["12"]["estado"] == "enviado"
    assert estado[v.id]["24"]["canales"] == {"correo": "ok", "google_chat": "deshabilitado"}
    assert estado[v.id]["24"]["momento"] == "2026-10-03T09:17:00-03:00"
    assert (config.base / estado[v.id]["12"]["snapshot"]).exists()


def test_fallo_de_canal_queda_registrado_y_se_reintenta(config, tmp_path):
    v = nueva_visita(config)
    fabricas = []
    r = motor(config, tmp_path, correo=CorreoFalso(fallar=True), fabricas=fabricas).ejecutar(local("2026-10-03T09:17"))
    assert r.acciones[0].estado == "error"
    assert r.proximo == local("2026-10-03T10:17")  # reintento en una hora
    reg = EstadoEnvios(config.rutas.envios_json).hito(v.id, 24)
    assert reg.canales["correo"].startswith("error: correo sin configurar")
    # Próxima hora: se reintenta con el snapshot guardado (sin volver a consultar fuentes).
    correo = CorreoFalso()
    r = motor(config, tmp_path, correo=correo, fabricas=fabricas).ejecutar(local("2026-10-03T10:17"))
    assert [(a.hito, a.tipo, a.estado) for a in r.acciones] == [(24, "reintentar", "enviado")]
    assert len(fabricas) == 1 and "Generado: sábado 03/10/2026 09:17" in correo.enviados[0][2]


def test_parcial_reintenta_solo_el_canal_que_fallo(config, tmp_path):
    config.ajustes.canales["google_chat"].habilitado = True
    v = nueva_visita(config, chat=True)
    correo, chat = CorreoFalso(), ChatFalso(fallar=True)
    r = motor(config, tmp_path, correo=correo, chat=chat).ejecutar(local("2026-10-03T09:17"))
    assert r.acciones[0].estado == "parcial"
    chat_ok = ChatFalso()
    r = motor(config, tmp_path, correo=correo, chat=chat_ok).ejecutar(local("2026-10-03T10:17"))
    assert r.acciones[0].estado == "enviado"
    assert len(correo.enviados) == 1  # el correo no se repite
    assert chat_ok.enviados[0][0] == f"{v.id}-24"


def test_falla_inesperada_no_frena_otras_visitas(config, tmp_path, monkeypatch):
    v1 = nueva_visita(config)
    v2 = nueva_visita(config, desde="15:00", hasta="17:00")
    import interfaz4.motor as modulo

    original = modulo.recolectar

    def recolectar_que_falla(config_, visita, *a, **k):
        if visita.id == v1.id:
            raise RuntimeError("se cortó la red")
        return original(config_, visita, *a, **k)

    monkeypatch.setattr(modulo, "recolectar", recolectar_que_falla)
    r = motor(config, tmp_path).ejecutar(local("2026-10-03T15:17"))
    estados = {a.visita_id: a.estado for a in r.acciones}
    assert estados == {v1.id: "error", v2.id: "enviado"}
    assert "RuntimeError" in EstadoEnvios(config.rutas.envios_json).hito(v1.id, 24).detalle


# ------------------------------------------------------------ CLI end-to-end


@pytest.fixture
def smtp_local():
    import socket

    from aiosmtpd.controller import Controller

    class Capturador:
        def __init__(self):
            self.mensajes = []

        async def handle_DATA(self, server, session, envelope):
            self.mensajes.append(envelope)
            return "250 OK"

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    handler = Capturador()
    controller = Controller(handler, hostname="127.0.0.1", port=puerto)
    controller.start()
    yield puerto, handler
    controller.stop()


def test_cli_end_to_end_con_ahora(proyecto, tmp_path, monkeypatch, smtp_local):
    """Definición de terminado: una visita de prueba genera y envía el informe
    de 24 h y el de 12 h en los momentos correctos (probado con --ahora)."""
    import email
    import email.policy

    from interfaz4 import cli
    import interfaz4.motor as modulo

    puerto, servidor = smtp_local
    for k, v in {
        "SMTP_HOST": "127.0.0.1",
        "SMTP_PORT": str(puerto),
        "SMTP_SEGURIDAD": "ninguna",
        "SMTP_USUARIO": "motor@example.com",
        "CORREO_DESTINO_POR_DEFECTO": "apicultor@example.com",
    }.items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(modulo, "construir_recolector", lambda config: recolector_offline(tmp_path, alertas=[]))
    runner = CliRunner()
    base = ["--base", str(proyecto)]

    r = runner.invoke(cli.app, ["planificar", "--apiario", "produccion_miel", "--fecha", "2026-10-04", "--desde", "09:00", "--hasta", "13:00", "--responsable", "Eduardo Mendoza", "--notas", "Revisión de núcleos", "--ahora", "2026-10-02T12:00-03:00", *base])
    assert r.exit_code == 0, r.output
    assert "Visita registrada: 2026-10-04-produccion_miel-01" in r.output
    assert "Informe 24 h: aprox. sábado 03/10/2026 09:00" in r.output

    salidas = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(salidas))
    r = runner.invoke(cli.app, ["ejecutar", "--ahora", "2026-10-03T08:17-03:00", *base])
    assert r.exit_code == 0 and "Sin hitos vencidos" in r.output and servidor.mensajes == []
    # El workflow programa la espera hasta el próximo envío con esta salida.
    assert salidas.read_text().splitlines() == ["proximo=2026-10-03T09:00:00-03:00"]

    r = runner.invoke(cli.app, ["ejecutar", "--ahora", "2026-10-03T09:17-03:00", *base])
    assert r.exit_code == 0, r.output
    assert "informe 24 h (enviar) → enviado" in r.output
    r = runner.invoke(cli.app, ["ejecutar", "--ahora", "2026-10-03T10:17-03:00", *base])
    assert "Sin hitos vencidos" in r.output
    r = runner.invoke(cli.app, ["ejecutar", "--ahora", "2026-10-03T21:17-03:00", *base])
    assert "informe 12 h (enviar) → enviado" in r.output
    assert salidas.read_text().splitlines()[-1] == "proximo="  # nada más que programar

    asuntos = [email.message_from_bytes(m.content, policy=email.policy.default)["Subject"] for m in servidor.mensajes]
    assert asuntos == [
        "🐝 Visita Apiario de producción melífera 04/10 09:00–13:00 · informe 24 h",
        "🐝 Visita Apiario de producción melífera 04/10 09:00–13:00 · informe 12 h",
    ]
    r = runner.invoke(cli.app, ["listar", "--ahora", "2026-10-03T22:00-03:00", *base])
    assert "24 h: enviado · 12 h: enviado" in r.output

    publico = json.loads((proyecto / "publico" / "estado.json").read_text())
    [vis] = publico["visitas"]
    assert [h["estado"] for h in vis["hitos"]] == ["enviado", "enviado"]
    assert (proyecto / "publico" / vis["hitos"][1]["informe"]).exists()

    r = runner.invoke(cli.app, ["cancelar", "2026-10-04-produccion_miel-01", *base])
    assert r.exit_code == 0 and "cancelada" in r.output


def test_cli_planificar_invalido(proyecto):
    from interfaz4 import cli

    r = CliRunner().invoke(cli.app, ["planificar", "--apiario", "produccion_miel", "--fecha", "2026-10-04", "--desde", "13:00", "--hasta", "09:00", "--ahora", "2026-10-02T12:00-03:00", "--base", str(proyecto)])
    assert r.exit_code == 1 and "posterior" in r.output


def test_listar_usa_el_reloj_real(proyecto, entorno):
    import time_machine

    from interfaz4 import cli

    config = cargar_config(proyecto, entorno)
    nueva_visita(config)
    runner = CliRunner()
    with time_machine.travel(datetime(2026, 10, 3, 12, 0, tzinfo=UTC)):
        assert "2026-10-04-produccion_miel-01" in runner.invoke(cli.app, ["listar", "--base", str(proyecto)]).output
    with time_machine.travel(datetime(2026, 10, 5, 12, 0, tzinfo=UTC)):
        assert "No hay visitas planificadas" in runner.invoke(cli.app, ["listar", "--base", str(proyecto)]).output
