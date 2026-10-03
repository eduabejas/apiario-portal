"""Envío a Google Chat por webhook entrante (requiere Google Workspace con
webhooks habilitados). Los mensajes largos llegan ya divididos y se agrupan
en un mismo hilo con threadKey."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

import httpx

from interfaz4.notificar import ErrorEnvio

log = logging.getLogger(__name__)


class EnviadorGoogleChat:
    def __init__(
        self,
        webhook_url: str | None,
        cliente: httpx.Client | None = None,
        pausa_seg: float = 1.0,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.url = webhook_url
        self.cliente = cliente or httpx.Client(timeout=30)
        self.pausa = pausa_seg
        self.dormir = dormir

    def enviar(self, mensajes: list[str], hilo: str | None = None) -> None:
        if not self.url:
            raise ErrorEnvio("Google Chat sin configurar: falta el secreto GCHAT_WEBHOOK_URL")
        # El webhook ya trae key y token en la query: se agregan parámetros sin pisarlos.
        url = httpx.URL(self.url)
        if hilo:
            url = url.copy_merge_params({"threadKey": hilo, "messageReplyOption": "REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"})
        for i, texto in enumerate(mensajes):
            if i:
                self.dormir(self.pausa)
            try:
                resp = self.cliente.post(
                    url,
                    json={"text": texto},
                    headers={"Content-Type": "application/json; charset=UTF-8"},
                )
            except httpx.HTTPError as e:
                raise ErrorEnvio(f"Google Chat: {type(e).__name__}: {e}") from e
            if resp.status_code != 200:
                raise ErrorEnvio(f"Google Chat respondió HTTP {resp.status_code} en el mensaje {i + 1} de {len(mensajes)}")
        log.info("Google Chat: %d mensaje(s) enviados", len(mensajes))
