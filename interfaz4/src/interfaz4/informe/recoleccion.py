"""Recolección de datos para un informe: consulta las fuentes habilitadas
(con caché en memoria por coordenada + ventana) y arma el snapshot."""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import BaseModel, Field

from interfaz4 import tiempo
from interfaz4.config import Config
from interfaz4.fuentes.base import Fuente, Reloj, Variables, reloj_real
from interfaz4.fuentes.http import ClienteHTTP
from interfaz4.fuentes.smn_cap import FuenteAlertasSMN
from interfaz4.modelos import Apiario, ResultadoAlertas, SerieFuente, Visita

log = logging.getLogger(__name__)

ORDEN_FUENTES = ("smn_wrf", "metno", "open_meteo", "ecmwf_ens")
VERSION_SNAPSHOT = 1


class DatosInforme(BaseModel):
    """Todo lo necesario para reconstruir un informe (se guarda como snapshot)."""

    version: int = VERSION_SNAPSHOT
    visita: Visita
    apiario: Apiario
    hito: int
    generado: datetime
    proximo_informe: datetime | None = None
    series: list[SerieFuente] = Field(default_factory=list)
    tramo_desde: datetime | None = None
    tramo_hasta: datetime | None = None
    series_previas: list[SerieFuente] = Field(default_factory=list)
    alertas: ResultadoAlertas | None = None  # None = fuente de alertas deshabilitada
    fuentes_deshabilitadas: list[str] = Field(default_factory=list)


class Recolector:
    """Fuentes habilitadas + caché en memoria por (fuente, coordenada, ventana)."""

    def __init__(self, fuentes: dict[str, Fuente], alertas: FuenteAlertasSMN | None) -> None:
        self.fuentes = {n: fuentes[n] for n in ORDEN_FUENTES if n in fuentes}
        self.fuente_alertas = alertas
        self._series: dict[tuple, SerieFuente] = {}
        self._alertas: dict[tuple, ResultadoAlertas] = {}

    def serie(self, nombre: str, apiario: Apiario, inicio: datetime, fin: datetime, variables: Variables) -> SerieFuente:
        clave = (nombre, apiario.lat, apiario.lon, inicio, fin, variables)
        if clave not in self._series:
            log.info("Consultando %s para %s (%s → %s, %s)", nombre, apiario.id, inicio, fin, variables)
            self._series[clave] = self.fuentes[nombre].obtener(apiario, inicio, fin, variables=variables)
        return self._series[clave]

    def alertas(self, apiario: Apiario, inicio: datetime, fin: datetime) -> ResultadoAlertas | None:
        if self.fuente_alertas is None:
            return None
        clave = (apiario.lat, apiario.lon, inicio, fin)
        if clave not in self._alertas:
            self._alertas[clave] = self.fuente_alertas.obtener(apiario, inicio, fin)
        return self._alertas[clave]


def construir_recolector(config: Config, reloj: Reloj = reloj_real) -> Recolector:
    """Instancia solo las fuentes habilitadas en config/ajustes.yaml."""
    from interfaz4.fuentes.metno import CacheMetno, FuenteMETNorway
    from interfaz4.fuentes.open_meteo import FuenteOpenMeteo
    from interfaz4.fuentes.smn_wrf import CacheGrilla, FuenteSMNWRF, RepositorioWRF

    ajustes = config.ajustes
    rutas = config.rutas
    http = ClienteHTTP(ajustes.reintentos, user_agent=config.secretos.metno_user_agent)
    fuentes: dict[str, Fuente] = {}
    if ajustes.fuente_habilitada("smn_wrf"):
        fuentes["smn_wrf"] = FuenteSMNWRF(RepositorioWRF(), CacheGrilla(rutas.cache_grilla_json), reloj)
    if ajustes.fuente_habilitada("metno"):
        fuentes["metno"] = FuenteMETNorway(http, CacheMetno(rutas.cache_metno_json), reloj)
    if ajustes.fuente_habilitada("open_meteo"):
        fuentes["open_meteo"] = FuenteOpenMeteo(http, reloj)
    if ajustes.fuente_habilitada("ecmwf_ens"):
        log.warning("ecmwf_ens está habilitada pero aún no está implementada (Fase 7): se ignora")
    alertas = FuenteAlertasSMN(http, reloj) if ajustes.fuente_habilitada("smn_cap") else None
    return Recolector(fuentes, alertas)


def recolectar(config: Config, visita: Visita, hito: int, ahora: datetime, recolector: Recolector) -> DatosInforme:
    apiario = config.apiario(visita.apiario)
    ahora = tiempo.a_local(ahora)
    inicio_filas = tiempo.piso_hora(visita.inicio)
    fin_filas = tiempo.techo_hora(visita.fin)
    series = [recolector.serie(n, apiario, inicio_filas, fin_filas, "todas") for n in recolector.fuentes]

    tramo_desde = tramo_hasta = None
    series_previas: list[SerieFuente] = []
    if config.ajustes.informe.incluir_tramo_previo:
        desde = tiempo.piso_hora(ahora)
        if desde < inicio_filas:
            tramo_desde, tramo_hasta = desde, inicio_filas
            series_previas = [
                recolector.serie(n, apiario, tramo_desde, tramo_hasta, "precipitacion") for n in recolector.fuentes
            ]

    siguientes = [h for h in config.ajustes.hitos_horas if h < hito]
    proximo = tiempo.sumar_horas(visita.inicio, -max(siguientes)) if siguientes else None
    deshabilitadas = [n for n in ORDEN_FUENTES if not config.ajustes.fuente_habilitada(n)]
    return DatosInforme(
        visita=visita,
        apiario=apiario,
        hito=hito,
        generado=ahora,
        proximo_informe=proximo if proximo and proximo > ahora else None,
        series=series,
        tramo_desde=tramo_desde,
        tramo_hasta=tramo_hasta,
        series_previas=series_previas,
        alertas=recolector.alertas(apiario, visita.inicio, visita.fin),
        fuentes_deshabilitadas=deshabilitadas,
    )
