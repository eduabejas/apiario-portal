"""Canales de envío del informe: correo (obligatorio) y Google Chat (opcional)."""


class ErrorEnvio(Exception):
    """El canal no pudo entregar el informe (se reintenta en la próxima ejecución)."""
