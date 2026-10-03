import email
import email.policy
import smtplib

import httpx
import pytest
import respx
from aiosmtpd.controller import Controller

from interfaz4.config import cargar_secretos
from interfaz4.notificar import ErrorEnvio
from interfaz4.notificar.correo_smtp import EnviadorCorreo, armar_mensaje
from interfaz4.notificar.google_chat import EnviadorGoogleChat

ASUNTO = "🐝 Visita Apiario de producción melífera 04/10 09:00–13:00 · informe 12 h"
HTML = "<html><body><p>Informe <b>HTML</b> con tildes: lluvia, ráfaga</p></body></html>"
TEXTO = "Informe en texto plano con tildes: lluvia, ráfaga"


class Capturador:
    def __init__(self):
        self.mensajes = []

    async def handle_DATA(self, server, session, envelope):
        self.mensajes.append(envelope)
        return "250 OK"


def puerto_libre() -> int:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def servidor_smtp():
    handler = Capturador()
    controller = Controller(handler, hostname="127.0.0.1", port=puerto_libre())
    controller.start()
    try:
        yield controller, handler
    finally:
        controller.stop()


def test_correo_real_multipart_alternative(servidor_smtp):
    controller, handler = servidor_smtp
    secretos = cargar_secretos(
        {
            "SMTP_HOST": "127.0.0.1",
            "SMTP_PORT": str(controller.port),
            "SMTP_SEGURIDAD": "ninguna",
            "SMTP_USUARIO": "motor@example.com",
        }
    )
    EnviadorCorreo(secretos).enviar(ASUNTO, HTML, TEXTO, ["apicultor@example.com", "otra@example.com"])
    [sobre] = handler.mensajes
    assert sobre.rcpt_tos == ["apicultor@example.com", "otra@example.com"]
    msg = email.message_from_bytes(sobre.content, policy=email.policy.default)
    assert msg["Subject"] == ASUNTO
    assert msg["To"] == "apicultor@example.com, otra@example.com"
    assert "motor@example.com" in msg["From"] and "Interfaz 4" in msg["From"]
    assert msg.get_content_type() == "multipart/alternative"
    partes = {p.get_content_type(): p.get_content() for p in msg.iter_parts()}
    assert partes["text/plain"].strip() == TEXTO
    assert "<b>HTML</b>" in partes["text/html"]


class SMTPFalso:
    instancias: list = []

    def __init__(self, host, port, timeout=None, context=None):
        self.args = (host, port, timeout, context)
        self.llamadas = []
        SMTPFalso.instancias.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.llamadas.append("quit")

    def ehlo(self):
        self.llamadas.append("ehlo")

    def starttls(self, context=None):
        self.llamadas.append("starttls")

    def login(self, u, c):
        self.llamadas.append(("login", u, c))

    def send_message(self, msg):
        self.llamadas.append(("send", msg["To"]))


def test_gmail_usa_starttls_y_login_con_clave_de_aplicacion():
    SMTPFalso.instancias = []
    secretos = cargar_secretos(
        {"SMTP_USUARIO": "cuenta@gmail.com", "SMTP_CLAVE_APP": "abcd efgh ijkl mnop", "CORREO_DESTINO_POR_DEFECTO": "a@b.com"}
    )
    EnviadorCorreo(secretos, smtp=SMTPFalso).enviar(ASUNTO, HTML, TEXTO, ["a@b.com"])
    [srv] = SMTPFalso.instancias
    assert srv.args[:2] == ("smtp.gmail.com", 587)
    assert srv.llamadas == ["ehlo", "starttls", "ehlo", ("login", "cuenta@gmail.com", "abcdefghijklmnop"), ("send", "a@b.com"), "quit"]


def test_puerto_465_usa_ssl():
    SMTPFalso.instancias = []
    secretos = cargar_secretos({"SMTP_PORT": "465", "SMTP_USUARIO": "c@x.com", "SMTP_CLAVE_APP": "k"})
    EnviadorCorreo(secretos, smtp_ssl=SMTPFalso).enviar(ASUNTO, HTML, TEXTO, ["a@b.com"])
    [srv] = SMTPFalso.instancias
    assert srv.args[3] is not None  # contexto TLS
    assert srv.llamadas[0] == ("login", "c@x.com", "k")


def test_sin_configurar_falla_claro():
    with pytest.raises(ErrorEnvio, match="SMTP_USUARIO"):
        EnviadorCorreo(cargar_secretos({})).enviar(ASUNTO, HTML, TEXTO, ["a@b.com"])
    with pytest.raises(ErrorEnvio, match="destinatarios"):
        EnviadorCorreo(cargar_secretos({"SMTP_USUARIO": "c@x.com", "SMTP_CLAVE_APP": "k"})).enviar(ASUNTO, HTML, TEXTO, [])


def test_error_smtp_se_convierte_en_error_envio():
    class Rechaza(SMTPFalso):
        def login(self, u, c):
            raise smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted")

    secretos = cargar_secretos({"SMTP_USUARIO": "c@gmail.com", "SMTP_CLAVE_APP": "mala"})
    with pytest.raises(ErrorEnvio, match="contraseña de aplicación"):
        EnviadorCorreo(secretos, smtp=Rechaza).enviar(ASUNTO, HTML, TEXTO, ["a@b.com"])

    class SinRed(SMTPFalso):
        def __init__(self, *a, **k):
            raise OSError("Network is unreachable")

    with pytest.raises(ErrorEnvio, match="unreachable"):
        EnviadorCorreo(secretos, smtp=SinRed).enviar(ASUNTO, HTML, TEXTO, ["a@b.com"])


def test_armar_mensaje_cabeceras():
    msg = armar_mensaje(ASUNTO, HTML, TEXTO, "Interfaz 4 <m@example.com>", ["x@y.com"])
    assert msg["Message-ID"].endswith("@example.com>")
    assert msg["Date"]
    assert msg.is_multipart()


WEBHOOK = "https://chat.googleapis.com/v1/spaces/AAA/messages?key=k&token=t"


@respx.mock
def test_google_chat_envia_cada_mensaje_en_un_hilo():
    ruta = respx.post(url__startswith="https://chat.googleapis.com/v1/spaces/AAA/messages").mock(
        return_value=httpx.Response(200, json={})
    )
    pausas = []
    EnviadorGoogleChat(WEBHOOK, dormir=pausas.append).enviar(["uno", "dos"], hilo="visita-x-12")
    assert ruta.call_count == 2
    import json

    assert [json.loads(c.request.content)["text"] for c in ruta.calls] == ["uno", "dos"]
    params = ruta.calls[0].request.url.params
    assert params["threadKey"] == "visita-x-12"
    assert params["key"] == "k" and params["token"] == "t"  # no se pierden las credenciales del webhook
    assert pausas == [1.0]


@respx.mock
def test_google_chat_error_http():
    respx.post(url__startswith="https://chat.googleapis.com").mock(return_value=httpx.Response(403))
    with pytest.raises(ErrorEnvio, match="403"):
        EnviadorGoogleChat(WEBHOOK, dormir=lambda s: None).enviar(["uno"])


def test_google_chat_sin_configurar():
    with pytest.raises(ErrorEnvio, match="GCHAT_WEBHOOK_URL"):
        EnviadorGoogleChat(None).enviar(["uno"])
