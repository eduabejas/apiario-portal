"""Datos de prueba offline: recolector con el WRF real recortado, la
respuesta real de MET Norway (precargada en su caché) y alertas fijas."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import fsspec
import httpx

from interfaz4.config import AjustesReintentos
from interfaz4.fuentes.http import ClienteHTTP
from interfaz4.fuentes.metno import URL as URL_METNO
from interfaz4.fuentes.metno import CacheMetno, FuenteMETNorway
from interfaz4.fuentes.smn_cap import parsear_cap, superpone
from interfaz4.fuentes.smn_wrf import CacheGrilla, FuenteSMNWRF, RepositorioWRF
from interfaz4.informe.recoleccion import Recolector
from interfaz4.modelos import Alerta, ResultadoAlertas, Visita
from tests.conftest import FIXTURES

# 21:17 del sábado 03/10 (hora Argentina): hito de 12 h de una visita el domingo a las 09:00.
AHORA_12H = datetime(2026, 10, 4, 0, 17, tzinfo=UTC)


def alerta_berisso() -> Alerta:
    [ag] = parsear_cap((FIXTURES / "smn_cap_sintetica_berisso.xml").read_bytes())
    return ag.alerta


class AlertasFijas:
    def __init__(self, alertas: list[Alerta], disponible: bool = True, reloj=lambda: AHORA_12H) -> None:
        self.lista = alertas
        self.disponible = disponible
        self.reloj = reloj
        self.consultas = 0

    def obtener(self, apiario, inicio, fin) -> ResultadoAlertas:
        self.consultas += 1
        if not self.disponible:
            return ResultadoAlertas(disponible=False, errores=["El feed CAP del SMN respondió HTTP 403"], obtenido_utc=self.reloj())
        return ResultadoAlertas(
            disponible=True, alertas=[a for a in self.lista if superpone(a, inicio, fin)], obtenido_utc=self.reloj()
        )


def _sin_red(request: httpx.Request) -> httpx.Response:
    raise AssertionError(f"Los tests no deben salir a la red: {request.url}")


def recolector_offline(
    tmp_path: Path, ahora: datetime = AHORA_12H, alertas: list[Alerta] | None = None, alertas_disponibles: bool = True
) -> Recolector:
    reloj = lambda: ahora  # noqa: E731
    wrf = FuenteSMNWRF(
        RepositorioWRF(fs=fsspec.filesystem("file"), raiz=str(FIXTURES / "smn_wrf")),
        CacheGrilla(tmp_path / "cache_grilla.json"),
        reloj=reloj,
    )
    cache = CacheMetno(None)
    cache.guardar(
        f"{URL_METNO}?lat=-34.8892&lon=-57.8279",
        {
            "last_modified": "Sat, 03 Oct 2026 21:32:22 GMT",
            "expires": "2100-01-01T00:00:00+00:00",
            "cuerpo": json.loads((FIXTURES / "metno_compact.json").read_text(encoding="utf-8")),
        },
    )
    http = ClienteHTTP(AjustesReintentos(http_intentos=1), transport=httpx.MockTransport(_sin_red), dormir=lambda s: None)
    metno = FuenteMETNorway(http, cache, reloj=reloj)
    fuente_alertas = AlertasFijas(alertas if alertas is not None else [alerta_berisso()], alertas_disponibles, reloj)
    return Recolector({"smn_wrf": wrf, "metno": metno}, fuente_alertas)  # type: ignore[arg-type]


def visita_domingo(**cambios) -> Visita:
    datos = {
        "id": "2026-10-04-produccion_miel-01",
        "apiario": "produccion_miel",
        "fecha": "2026-10-04",
        "desde": "09:00",
        "hasta": "13:00",
        "responsable": "Eduardo Mendoza",
        "notas": "Revisión de núcleos",
    }
    datos.update(cambios)
    return Visita(**datos)
