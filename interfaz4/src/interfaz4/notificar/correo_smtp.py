"""Envío por correo: smtplib + STARTTLS (o SSL), multipart/alternative
(texto plano + HTML), destinatario por visita."""

from __future__ import annotations

import logging
import smtplib
import ssl
from collections.abc import Callable
from datetime import UTC, datetime
from email.headerregistry import Address
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid, parseaddr

from interfaz4.config import Secretos
from interfaz4.notificar import ErrorEnvio

log = logging.getLogger(__name__)

NOMBRE_REMITENTE = "Interfaz 4 · Apiario"


def remitente(secretos: Secretos) -> str:
    if secretos.smtp_remitente:
        return secretos.smtp_remitente
    return formataddr((NOMBRE_REMITENTE, secretos.smtp_usuario or ""))


def armar_mensaje(
    asunto: str, html: str, texto: str, de: str, para: list[str], ahora: datetime | None = None
) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = asunto
    msg["From"] = de
    msg["To"] = ", ".join(para)
    msg["Date"] = format_datetime(ahora or datetime.now(UTC))
    dominio = parseaddr(de)[1].rpartition("@")[2] or "interfaz4.local"
    msg["Message-ID"] = make_msgid(domain=dominio)
    msg.set_content(texto)
    msg.add_alternative(html, subtype="html")
    return msg


class EnviadorCorreo:
    def __init__(
        self,
        secretos: Secretos,
        smtp: Callable[..., smtplib.SMTP] = smtplib.SMTP,
        smtp_ssl: Callable[..., smtplib.SMTP_SSL] = smtplib.SMTP_SSL,
        timeout: float = 30.0,
    ) -> None:
        self.s = secretos
        self.smtp = smtp
        self.smtp_ssl = smtp_ssl
        self.timeout = timeout

    def verificar(self, destinatarios: list[str]) -> None:
        if self.s.smtp_seguridad != "ninguna" and not self.s.smtp_configurado:
            raise ErrorEnvio("correo sin configurar: faltan los secretos SMTP_USUARIO y/o SMTP_CLAVE_APP")
        if not destinatarios:
            raise ErrorEnvio("sin destinatarios: cargar CORREO_DESTINO_POR_DEFECTO o CORREOS_RESPONSABLES")
        for d in destinatarios:
            try:
                Address(addr_spec=d)
            except (ValueError, IndexError) as e:
                raise ErrorEnvio(f"destinatario inválido: {d!r}") from e

    def enviar(self, asunto: str, html: str, texto: str, destinatarios: list[str]) -> None:
        self.verificar(destinatarios)
        msg = armar_mensaje(asunto, html, texto, remitente(self.s), destinatarios)
        contexto = ssl.create_default_context()
        try:
            if self.s.smtp_seguridad == "ssl":
                with self.smtp_ssl(self.s.smtp_host, self.s.smtp_port, timeout=self.timeout, context=contexto) as srv:
                    srv.login(self.s.smtp_usuario, self.s.smtp_clave_app)
                    srv.send_message(msg)
            else:
                with self.smtp(self.s.smtp_host, self.s.smtp_port, timeout=self.timeout) as srv:
                    srv.ehlo()
                    if self.s.smtp_seguridad == "starttls":
                        srv.starttls(context=contexto)
                        srv.ehlo()
                        srv.login(self.s.smtp_usuario, self.s.smtp_clave_app)
                    srv.send_message(msg)
        except smtplib.SMTPAuthenticationError as e:
            raise ErrorEnvio(
                "el servidor SMTP rechazó usuario/clave (en Gmail hace falta una contraseña de aplicación)"
            ) from e
        except (smtplib.SMTPException, OSError) as e:
            raise ErrorEnvio(f"{type(e).__name__}: {e}") from e
        log.info("Correo enviado a %s: %s", ", ".join(destinatarios), asunto)
