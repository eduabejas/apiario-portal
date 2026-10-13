"""Cliente HTTP con reintentos, backoff, timeouts, lista blanca de hosts y
tope de tamaño (sin evadir protecciones)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping
from urllib.parse import urlparse

import httpx

from interfaz4.config import AjustesReintentos
from interfaz4.fuentes.base import ErrorFuente

log = logging.getLogger(__name__)

MARCAS_CHALLENGE = ("cf-chl", "just a moment", "challenge-platform", "attention required", "captcha")

# Las fuentes conocidas: cualquier otro host se rechaza aunque sea HTTPS.
HOSTS_PERMITIDOS = frozenset({
    "api.met.no",
    "ssl.smn.gob.ar",
    "api.open-meteo.com",
    "smn-ar-wrf.s3.amazonaws.com",
    "smn-ar-wrf.s3-us-west-2.amazonaws.com",
})
TOPE_RESPUESTA_BYTES = 5 * 1024 * 1024  # 5 MB
CONTENIDOS_ESPERADOS = ("application/json", "application/xml", "application/rss+xml", "text/xml")


def parece_challenge(resp: httpx.Response) -> bool:
    """403 o página HTML de verificación anti-bot. No se evade: se informa."""
    if "html" in resp.headers.get("content-type", "").lower():
        cuerpo = resp.text[:4000].lower()
        if any(marca in cuerpo for marca in MARCAS_CHALLENGE):
            return True
    return resp.status_code == 403


class ClienteHTTP:
    """GET con reintentos ante errores de red y 5xx. 4xx no se reintenta."""

    def __init__(
        self,
        reintentos: AjustesReintentos | None = None,
        user_agent: str | None = None,
        transport: httpx.BaseTransport | None = None,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.reintentos = reintentos or AjustesReintentos()
        self.dormir = dormir
        cabeceras = {"User-Agent": user_agent} if user_agent else {}
        self.cliente = httpx.Client(
            headers=cabeceras,
            timeout=self.reintentos.timeout_seg,
            follow_redirects=True,
            transport=transport,
        )

    def get(
        self,
        url: str,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in HOSTS_PERMITIDOS:
            raise ErrorFuente(f"host no permitido: {parsed.scheme}://{parsed.hostname}")
        intentos = self.reintentos.http_intentos
        esperas = self.reintentos.http_backoff_seg or [0.0]
        ultimo_error = "sin intentos"
        for intento in range(intentos):
            try:
                resp = self.cliente.get(url, params=params, headers=headers)
            except httpx.HTTPError as e:
                ultimo_error = f"{type(e).__name__}: {e}"
            else:
                # Redirecciones fuera de la lista blanca o cuerpo gigante → rechazo.
                destino = urlparse(str(resp.url))
                if destino.hostname not in HOSTS_PERMITIDOS:
                    raise ErrorFuente(f"redirección fuera de la lista blanca: {destino.hostname}")
                largo = resp.headers.get("content-length")
                if largo and largo.isdigit() and int(largo) > TOPE_RESPUESTA_BYTES:
                    raise ErrorFuente(f"respuesta demasiado grande: {int(largo)/1024/1024:.1f} MB > 5 MB")
                if len(resp.content) > TOPE_RESPUESTA_BYTES:
                    raise ErrorFuente(f"respuesta demasiado grande: {len(resp.content)/1024/1024:.1f} MB > 5 MB")
                if resp.status_code < 500 or parece_challenge(resp):
                    return resp
                ultimo_error = f"HTTP {resp.status_code}"
            if intento < intentos - 1:
                espera = esperas[min(intento, len(esperas) - 1)]
                log.warning("GET %s falló (%s); reintento %d en %.0f s", url, ultimo_error, intento + 2, espera)
                self.dormir(espera)
        raise ErrorFuente(f"{url}: {ultimo_error} tras {intentos} intentos")

    def cerrar(self) -> None:
        self.cliente.close()
