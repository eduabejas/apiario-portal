"""Fuente A — SMN Argentina, WRF-SMN determinístico (AWS Open Data).

Archivos horarios en s3://smn-ar-wrf (acceso anónimo):
    DATA/WRF/DET/{AAAA}/{MM}/{DD}/{CC}/WRFDETAR_01H_{AAAAMMDD}_{CC}_{PPP}.nc
Cada archivo trae un solo tiempo válido en init + PPP h (plazos 000–072,
verificado en Fase 0). Se leen solo los chunks de las variables necesarias en
el punto de grilla más cercano al apiario, con h5py sobre s3fs (≈15 MB por
archivo con las 5 variables; ≈2 MB si solo hace falta PP).

Convención: `PP` del archivo válido en t es la lluvia de (t−1h, t] → para la
fila H se usa el archivo válido en H+1 (verificado contra los archivos de
10 minutos). Las instantáneas se toman del archivo válido en H.
"""

from __future__ import annotations

import json
import logging
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np

from interfaz4 import normalizar, tiempo
from interfaz4.fuentes.base import Fuente, Reloj, Variables, reloj_real
from interfaz4.modelos import Apiario, SerieFuente

log = logging.getLogger(__name__)

BUCKET = "smn-ar-wrf"
REGION = "us-west-2"
PLAZO_MAX = 72
CICLOS_UTC = (18, 12, 6, 0)
INSTANTANEAS = ("T2", "HR2", "magViento10", "dirViento10")
PRECIPITACION = "PP"
RADIO_TIERRA_KM = 6371.0
_UNIDADES_TIEMPO = re.compile(r"^\s*(days|hours|minutes|seconds)\s+since\s+(.+?)\s*$")


@dataclass(frozen=True)
class LecturaWRF:
    valido_utc: datetime
    valores: dict[str, float | None]
    forma: tuple[int, int]


def _texto(attr: object) -> str:
    if isinstance(attr, bytes):
        return attr.decode("utf-8", "replace")
    if isinstance(attr, np.ndarray) and attr.size == 1:
        return _texto(attr.item())
    return str(attr)


def decodificar_tiempo(unidades: str, valor: float) -> datetime:
    """'hours since 2026-10-03T12:00:00' + 12 → 2026-10-04 00:00 UTC."""
    m = _UNIDADES_TIEMPO.match(unidades)
    if not m:
        raise ValueError(f"Unidades de tiempo no reconocidas: {unidades!r}")
    base = datetime.fromisoformat(m.group(2))
    if base.tzinfo is None:
        base = base.replace(tzinfo=UTC)
    return (base + timedelta(**{m.group(1): float(valor)})).astimezone(UTC)


def indice_mas_cercano(lat: np.ndarray, lon: np.ndarray, lat0: float, lon0: float) -> tuple[int, int, float]:
    """(iy, ix, distancia_km) del punto de grilla 2D más cercano (haversine)."""
    la1, lo1 = math.radians(lat0), math.radians(lon0)
    la2, lo2 = np.radians(lat.astype("f8")), np.radians(lon.astype("f8"))
    a = np.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    d = 2 * RADIO_TIERRA_KM * np.arcsin(np.sqrt(np.clip(a, 0, 1)))
    iy, ix = np.unravel_index(int(np.argmin(d)), d.shape)
    return int(iy), int(ix), float(d[iy, ix])


class RepositorioWRF:
    """Acceso a los archivos del WRF. En producción, S3 anónimo; en tests, un
    filesystem fsspec local con la misma estructura de carpetas."""

    def __init__(self, fs=None, raiz: str = BUCKET) -> None:
        self._fs = fs
        self.raiz = raiz.rstrip("/")

    @property
    def fs(self):
        if self._fs is None:
            import s3fs

            self._fs = s3fs.S3FileSystem(anon=True, client_kwargs={"region_name": REGION})
        return self._fs

    def dir_ciclo(self, init: datetime) -> str:
        return f"{self.raiz}/DATA/WRF/DET/{init:%Y/%m/%d}/{init:%H}"

    def ruta(self, init: datetime, plazo: int) -> str:
        return f"{self.dir_ciclo(init)}/WRFDETAR_01H_{init:%Y%m%d}_{init:%H}_{plazo:03d}.nc"

    def plazos_disponibles(self, init: datetime) -> set[int]:
        try:
            nombres = self.fs.ls(self.dir_ciclo(init), detail=False)
        except FileNotFoundError:
            return set()
        prefijo = f"WRFDETAR_01H_{init:%Y%m%d}_{init:%H}_"
        plazos: set[int] = set()
        for nombre in nombres:
            base = str(nombre).rstrip("/").rsplit("/", 1)[-1]
            if base.startswith(prefijo) and base.endswith(".nc") and base[len(prefijo) : -3].isdigit():
                plazos.add(int(base[len(prefijo) : -3]))
        return plazos

    def _abrir(self, ruta: str):
        # Sin caché de bloques: h5py pide solo metadatos y los chunks necesarios.
        return self.fs.open(ruta, "rb", block_size=2**18, cache_type="none")

    def leer(self, ruta: str, iy: int, ix: int, variables: list[str]) -> LecturaWRF:
        import h5py

        valores: dict[str, float | None] = {}
        with self._abrir(ruta) as f, h5py.File(f, "r") as h:
            t = h["time"]
            valido = decodificar_tiempo(_texto(t.attrs["units"]), float(np.asarray(t[...]).ravel()[0]))
            forma = tuple(int(n) for n in h["lat"].shape[-2:])
            for nombre in variables:
                if nombre not in h:
                    valores[nombre] = None
                    continue
                ds = h[nombre]
                dato = ds[0, iy, ix] if ds.ndim == 3 else ds[iy, ix]
                relleno = ds.attrs.get("_FillValue")
                if relleno is not None and np.any(np.asarray(relleno) == dato):
                    valores[nombre] = None
                else:
                    valores[nombre] = normalizar.valor(dato)
        return LecturaWRF(valido_utc=valido, valores=valores, forma=forma)  # type: ignore[arg-type]

    def leer_latlon(self, ruta: str) -> tuple[np.ndarray, np.ndarray]:
        import h5py

        with self._abrir(ruta) as f, h5py.File(f, "r") as h:
            return np.asarray(h["lat"][...]), np.asarray(h["lon"][...])


class CacheGrilla:
    """Índice (iy, ix) por coordenada, con la forma de la grilla como firma."""

    def __init__(self, ruta: Path | None) -> None:
        self.ruta = ruta

    def _leer(self) -> dict:
        if self.ruta and self.ruta.exists():
            try:
                return json.loads(self.ruta.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                log.warning("cache_grilla.json ilegible: se recalcula")
        return {}

    @staticmethod
    def clave(lat: float, lon: float) -> str:
        return f"{lat:.6f},{lon:.6f}"

    def obtener(self, lat: float, lon: float, forma: tuple[int, int]) -> dict | None:
        datos = self._leer()
        if tuple(datos.get("forma") or ()) != tuple(forma):
            return None
        return (datos.get("puntos") or {}).get(self.clave(lat, lon))

    def guardar(self, lat: float, lon: float, forma: tuple[int, int], punto: dict) -> None:
        if not self.ruta:
            return
        datos = self._leer()
        if tuple(datos.get("forma") or ()) != tuple(forma):
            datos = {"forma": list(forma), "puntos": {}}
        datos["puntos"][self.clave(lat, lon)] = punto
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(json.dumps(datos, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ciclos_candidatos(ahora_utc: datetime) -> list[datetime]:
    """Hoy y ayer, ciclos 18→12→06→00 UTC, del más reciente al más antiguo."""
    candidatos = []
    for dias in (0, 1):
        dia = (ahora_utc - timedelta(days=dias)).date()
        for cc in CICLOS_UTC:
            init = datetime(dia.year, dia.month, dia.day, cc, tzinfo=UTC)
            if init <= ahora_utc:
                candidatos.append(init)
    return candidatos


class FuenteSMNWRF(Fuente):
    nombre = "smn_wrf"
    etiqueta = "SMN WRF"

    def __init__(
        self,
        repositorio: RepositorioWRF | None = None,
        cache_grilla: CacheGrilla | None = None,
        reloj: Reloj = reloj_real,
    ) -> None:
        super().__init__(reloj)
        self.repo = repositorio or RepositorioWRF()
        self.cache_grilla = cache_grilla or CacheGrilla(None)
        self._plazos: dict[datetime, set[int]] = {}
        self._memo: dict[tuple[str, int, int, str], float | None] = {}
        self._indices: dict[tuple[float, float], tuple[int, int, tuple[int, int]]] = {}

    # ----------------------------------------------------------- ciclos

    def plazos(self, init: datetime) -> set[int]:
        if init not in self._plazos:
            self._plazos[init] = self.repo.plazos_disponibles(init)
        return self._plazos[init]

    def elegir_ciclo(self, ahora_utc: datetime, ultimo_valido_utc: datetime) -> tuple[datetime, set[int]] | None:
        """Ciclo más reciente que tenga el archivo del plazo máximo necesario.

        Si ninguno lo tiene (ventana más allá de +72 h), se usa el más
        reciente con archivos y las horas sin dato quedan en s/d.
        """
        primero: tuple[datetime, set[int]] | None = None
        for init in ciclos_candidatos(ahora_utc):
            disponibles = self.plazos(init)
            if not disponibles:
                continue
            if primero is None:
                primero = (init, disponibles)
            plazo_max = math.ceil((ultimo_valido_utc - init).total_seconds() / 3600)
            if plazo_max in disponibles:
                return init, disponibles
        return primero

    # ----------------------------------------------------------- grilla

    def indice(self, apiario: Apiario, ruta_muestra: str) -> tuple[int, int]:
        clave = (apiario.lat, apiario.lon)
        if clave in self._indices:
            iy, ix, _ = self._indices[clave]
            return iy, ix
        lectura = self.repo.leer(ruta_muestra, 0, 0, [])
        cacheado = self.cache_grilla.obtener(apiario.lat, apiario.lon, lectura.forma)
        if cacheado:
            iy, ix = int(cacheado["iy"]), int(cacheado["ix"])
        else:
            lat, lon = self.repo.leer_latlon(ruta_muestra)
            iy, ix, dist = indice_mas_cercano(lat, lon, apiario.lat, apiario.lon)
            self.cache_grilla.guardar(
                apiario.lat,
                apiario.lon,
                lectura.forma,
                {
                    "iy": iy,
                    "ix": ix,
                    "dist_km": round(dist, 3),
                    "lat_grilla": round(float(lat[iy, ix]), 6),
                    "lon_grilla": round(float(lon[iy, ix]), 6),
                },
            )
            log.info("Punto de grilla WRF para %s: (%d, %d) a %.2f km", apiario.id, iy, ix, dist)
        self._indices[clave] = (iy, ix, lectura.forma)
        return iy, ix

    # ----------------------------------------------------------- lectura

    def _leer_punto(self, ruta: str, iy: int, ix: int, variables: list[str], esperado: datetime) -> dict[str, float | None]:
        faltan = [v for v in variables if (ruta, iy, ix, v) not in self._memo]
        if faltan:
            lectura = self.repo.leer(ruta, iy, ix, faltan)
            if lectura.valido_utc != esperado:
                raise ValueError(f"tiempo válido {lectura.valido_utc:%Y-%m-%d %H} UTC, se esperaba {esperado:%Y-%m-%d %H} UTC")
            for v in faltan:
                self._memo[(ruta, iy, ix, v)] = lectura.valores.get(v)
        return {v: self._memo[(ruta, iy, ix, v)] for v in variables}

    def obtener(
        self, apiario: Apiario, inicio: datetime, fin: datetime, variables: Variables = "todas"
    ) -> SerieFuente:
        filas = tiempo.rango_horas(inicio, fin)
        if not filas:
            return self.serie_vacia(inicio, fin)
        necesidades: dict[datetime, set[str]] = {}
        for h in filas:
            if variables == "todas":
                necesidades.setdefault(tiempo.a_utc(h), set()).update(INSTANTANEAS)
            necesidades.setdefault(tiempo.a_utc(tiempo.sumar_horas(h, 1)), set()).add(PRECIPITACION)
        try:
            eleccion = self.elegir_ciclo(tiempo.a_utc(self.reloj()), max(necesidades))
        except Exception as e:  # red, permisos, etc.
            log.exception("SMN WRF: no se pudo listar el bucket")
            return self.serie_vacia(inicio, fin, f"SMN WRF no disponible: {type(e).__name__}: {e}")
        if eleccion is None:
            return self.serie_vacia(inicio, fin, "SMN WRF: no hay ciclos publicados en las últimas 48 h")
        init, disponibles = eleccion
        errores: list[str] = []
        lecturas: dict[datetime, dict[str, float | None]] = {}
        fuera_de_alcance = []
        a_leer = []
        for t, variables in sorted(necesidades.items()):
            plazo = (t - init).total_seconds() / 3600
            if plazo.is_integer() and int(plazo) in disponibles and 0 <= plazo <= PLAZO_MAX:
                a_leer.append((t, int(plazo), sorted(variables)))
            else:
                fuera_de_alcance.append(t)
        if a_leer:
            try:
                iy, ix = self.indice(apiario, self.repo.ruta(init, a_leer[0][1]))
            except Exception as e:
                log.exception("SMN WRF: no se pudo determinar el punto de grilla")
                return self.serie_vacia(inicio, fin, f"SMN WRF: error al ubicar el punto de grilla: {e}")
            for t, plazo, variables in a_leer:
                ruta = self.repo.ruta(init, plazo)
                try:
                    lecturas[t] = self._leer_punto(ruta, iy, ix, variables, t)
                except Exception as e:
                    log.warning("SMN WRF: falló %s: %s", ruta, e)
                    errores.append(f"plazo {plazo:03d}: {type(e).__name__}: {e}")
        if fuera_de_alcance:
            errores.append(
                f"{len(fuera_de_alcance)} horas fuera de lo publicado por el ciclo {tiempo.fmt_utc_ciclo(init)} "
                f"(plazos 000–{max(disponibles):03d}): quedan en s/d"
            )
        instantaneos = {
            t: {
                "temp_c": v.get("T2"),
                "hr_pct": v.get("HR2"),
                "viento_kmh": normalizar.ms_a_kmh(v.get("magViento10")),
                "viento_dir_grados": v.get("dirViento10"),
            }
            for t, v in lecturas.items()
            if any(k in v for k in INSTANTANEAS)
        }
        acumulados = {t: {"precip_mm": v.get(PRECIPITACION)} for t, v in lecturas.items() if PRECIPITACION in v}
        return SerieFuente(
            fuente="smn_wrf",
            emitido_utc=init,
            obtenido_utc=self.reloj(),
            puntos=normalizar.armar_puntos(filas, instantaneos, acumulados, normalizar.Convencion.HORA_QUE_TERMINA),
            errores=errores,
            detalle_emision=f"ciclo {tiempo.fmt_utc_ciclo(init)}",
        )
