"""Fuente B — MET Norway Locationforecast 2.0 (compact).

- Exige un User-Agent identificatorio (sin él responde 403).
- Coordenadas con 4 decimales como máximo.
- Respeta la caché: guarda Last-Modified/Expires, no repite antes de Expires
  y revalida con If-Modified-Since (304 → se reutiliza el cuerpo guardado).
- 429 → se frena (no se reintenta); 203 → producto deprecado/beta (aviso).
- Fuera de la región nórdica no hay probability_of_precipitation ni
  wind_speed_of_gust: no se buscan.

Convención: `next_1_hours.precipitation_amount` en t es la lluvia de
[t, t+1h) (hora que empieza) → la fila H usa el timestamp H.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

from interfaz4 import normalizar, tiempo
from interfaz4.fuentes.base import ErrorFuente, Fuente, Reloj, Variables, reloj_real
from interfaz4.fuentes.http import ClienteHTTP
from interfaz4.modelos import Apiario, SerieFuente

log = logging.getLogger(__name__)

URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"


def _fecha_http(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        dt = parsedate_to_datetime(valor)
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _iso(texto: str | None) -> datetime | None:
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None


class CacheMetno:
    """Caché en disco por URL (Last-Modified, Expires y cuerpo JSON)."""

    def __init__(self, ruta: Path | None) -> None:
        self.ruta = ruta
        self._datos: dict | None = None

    def _todo(self) -> dict:
        if self._datos is None:
            self._datos = {}
            if self.ruta and self.ruta.exists():
                try:
                    self._datos = json.loads(self.ruta.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    log.warning("cache_metno.json ilegible: se ignora")
        return self._datos

    def obtener(self, clave: str) -> dict | None:
        return self._todo().get(clave)

    def guardar(self, clave: str, entrada: dict) -> None:
        self._todo()[clave] = entrada
        if self.ruta:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            self.ruta.write_text(json.dumps(self._todo(), ensure_ascii=False) + "\n", encoding="utf-8")


class FuenteMETNorway(Fuente):
    nombre = "metno"
    etiqueta = "MET Norway"

    def __init__(self, http: ClienteHTTP, cache: CacheMetno | None = None, reloj: Reloj = reloj_real) -> None:
        super().__init__(reloj)
        self.http = http
        self.cache = cache or CacheMetno(None)
        self._frenada: str | None = None
        self._memoria: dict[str, tuple[dict, list[str]]] = {}

    @staticmethod
    def parametros(apiario: Apiario) -> dict[str, str]:
        lat, lon = apiario.coord_4
        return {"lat": f"{lat:.4f}", "lon": f"{lon:.4f}"}

    def consultar(self, apiario: Apiario) -> tuple[dict, list[str]]:
        """JSON del producto compact + avisos. Lanza ErrorFuente si no hay datos."""
        params = self.parametros(apiario)
        clave = f"{URL}?lat={params['lat']}&lon={params['lon']}"
        if clave in self._memoria:
            return self._memoria[clave]
        if self._frenada:
            raise ErrorFuente(self._frenada)
        ahora = self.reloj()
        entrada = self.cache.obtener(clave)
        avisos: list[str] = []
        expira = _iso(entrada.get("expires")) if entrada else None
        if entrada and expira and ahora < expira:
            log.info("MET Norway: uso la respuesta guardada (vigente hasta %s)", expira.isoformat())
            resultado = (entrada["cuerpo"], avisos)
            self._memoria[clave] = resultado
            return resultado
        cabeceras = {}
        if entrada and entrada.get("last_modified"):
            cabeceras["If-Modified-Since"] = entrada["last_modified"]
        try:
            resp = self.http.get(URL, params=params, headers=cabeceras)
        except ErrorFuente as e:
            # Sin red hacia MET Norway: no se insiste en el resto de la ejecución.
            self._frenada = f"MET Norway no respondió: {e}"
            raise ErrorFuente(self._frenada) from e
        if resp.status_code == 304 and entrada:
            cuerpo = entrada["cuerpo"]
            last_modified = entrada.get("last_modified")
        elif resp.status_code in (200, 203):
            try:
                cuerpo = resp.json()
            except ValueError as e:
                raise ErrorFuente(f"MET Norway: respuesta no es JSON ({e})") from e
            last_modified = resp.headers.get("last-modified")
            if resp.status_code == 203:
                aviso = "MET Norway respondió 203: el producto está deprecado o en beta (revisar api.met.no)"
                log.warning(aviso)
                avisos.append(aviso)
        elif resp.status_code == 429:
            self._frenada = "MET Norway respondió 429 (demasiadas solicitudes): se frena hasta la próxima ejecución"
            raise ErrorFuente(self._frenada)
        elif resp.status_code == 403:
            self._frenada = "MET Norway respondió 403 (User-Agent o coordenadas rechazados): fuente deshabilitada en esta ejecución"
            raise ErrorFuente(self._frenada)
        else:
            raise ErrorFuente(f"MET Norway respondió HTTP {resp.status_code}")
        expires = _fecha_http(resp.headers.get("expires"))
        self.cache.guardar(
            clave,
            {
                "last_modified": last_modified,
                "expires": expires.isoformat() if expires else None,
                "guardado_utc": ahora.isoformat(),
                "cuerpo": cuerpo,
            },
        )
        resultado = (cuerpo, avisos)
        self._memoria[clave] = resultado
        return resultado

    def obtener(
        self, apiario: Apiario, inicio: datetime, fin: datetime, variables: Variables = "todas"
    ) -> SerieFuente:
        filas = tiempo.rango_horas(inicio, fin)
        try:
            cuerpo, avisos = self.consultar(apiario)
            propiedades = cuerpo["properties"]
            serie = propiedades["timeseries"]
        except ErrorFuente as e:
            return self.serie_vacia(inicio, fin, str(e))
        except (KeyError, TypeError) as e:
            return self.serie_vacia(inicio, fin, f"MET Norway: formato inesperado ({e})")
        instantaneos: dict[datetime, dict] = {}
        acumulados: dict[datetime, dict] = {}
        for paso in serie:
            t = _iso(paso.get("time"))
            datos = paso.get("data") or {}
            if t is None:
                continue
            det = (datos.get("instant") or {}).get("details") or {}
            instantaneos[t] = {
                "temp_c": det.get("air_temperature"),
                "hr_pct": det.get("relative_humidity"),
                "viento_kmh": normalizar.ms_a_kmh(det.get("wind_speed")),
                "viento_dir_grados": det.get("wind_from_direction"),
            }
            proxima = (datos.get("next_1_hours") or {}).get("details") or {}
            if "precipitation_amount" in proxima:
                acumulados[t] = {"precip_mm": proxima.get("precipitation_amount")}
        emitido = _iso((propiedades.get("meta") or {}).get("updated_at"))
        return SerieFuente(
            fuente="metno",
            emitido_utc=emitido,
            obtenido_utc=self.reloj(),
            puntos=normalizar.armar_puntos(filas, instantaneos, acumulados, normalizar.Convencion.HORA_QUE_EMPIEZA),
            errores=avisos,
            detalle_emision=f"actualizado {tiempo.fmt_dd_mm(tiempo.a_utc(emitido))} {tiempo.fmt_hora(tiempo.a_utc(emitido))} UTC" if emitido else None,
        )
