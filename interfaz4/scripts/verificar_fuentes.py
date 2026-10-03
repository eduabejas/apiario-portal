#!/usr/bin/env python3
"""Fase 0 — verificación de fuentes (spike, sin código de producción).

Para la coordenada del apiario, consulta cada fuente habilitada, guarda
respuestas reales en tests/fixtures/ y escribe un reporte en Markdown con lo
observado (variables, convenciones de intervalos, bytes, tiempos, bloqueos).

Uso (desde interfaz4/):
    uv run python scripts/verificar_fuentes.py
    uv run python scripts/verificar_fuentes.py --fuentes metno,smn_cap
    uv run python scripts/verificar_fuentes.py --open-meteo   # solo si el usuario lo autoriza

No evade protecciones anti-bot: si una fuente responde 403 o un challenge, se
registra y se sigue con la siguiente.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import platform
import sys
import time
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path

LAT = -34.889180362505506
LON = -57.82789829443907
UA_POR_DEFECTO = "interfaz4-apiarios/0.1 (+https://github.com/eduabejas/apiario-portal)"
CAP_FEED = "https://ssl.smn.gob.ar/CAP/AR.php"
METNO_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
BUCKET = "smn-ar-wrf"
CAP_NS = {"cap": "urn:oasis:names:tc:emergency:cap:1.2"}

BASE = Path(__file__).resolve().parent.parent


class Reporte:
    """Acumula líneas de Markdown y las imprime a medida que llegan."""

    def __init__(self) -> None:
        self.lineas: list[str] = []

    def __call__(self, texto: str = "") -> None:
        print(texto, flush=True)
        self.lineas.append(texto)

    def bloque(self, texto: str, lenguaje: str = "") -> None:
        self(f"```{lenguaje}")
        for linea in texto.rstrip("\n").splitlines():
            self(linea)
        self("```")

    def texto(self) -> str:
        return "\n".join(self.lineas) + "\n"


class Contador(io.RawIOBase):
    """Envuelve un archivo remoto para contar bytes efectivamente leídos."""

    def __init__(self, f) -> None:
        self.f = f
        self.bytes = 0
        self.lecturas = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def seek(self, *args):
        return self.f.seek(*args)

    def tell(self) -> int:
        return self.f.tell()

    def readinto(self, b) -> int:
        datos = self.f.read(len(b))
        n = len(datos)
        b[:n] = datos
        self.bytes += n
        self.lecturas += 1
        return n

    def read(self, n: int = -1) -> bytes:
        datos = self.f.read(n)
        self.bytes += len(datos)
        self.lecturas += 1
        return datos


def ua() -> str:
    return os.environ.get("METNO_USER_AGENT") or UA_POR_DEFECTO


# --------------------------------------------------------------------------
# A — SMN WRF (AWS Open Data)
# --------------------------------------------------------------------------


def verificar_smn_wrf(r: Reporte) -> None:
    import numpy as np
    import s3fs
    import xarray as xr

    r("## A — SMN WRF-SMN determinístico (s3://smn-ar-wrf)")
    r()
    fs = s3fs.S3FileSystem(anon=True, client_kwargs={"region_name": "us-west-2"})
    ahora = datetime.now(UTC)
    ciclos = []
    for dias in (0, 1):
        dia = (ahora - timedelta(days=dias)).date()
        for cc in (18, 12, 6, 0):
            init = datetime(dia.year, dia.month, dia.day, cc, tzinfo=UTC)
            if init > ahora:
                continue
            prefijo = f"{BUCKET}/DATA/WRF/DET/{dia:%Y/%m/%d}/{cc:02d}/"
            try:
                entradas = fs.ls(prefijo, detail=True, refresh=True)
            except FileNotFoundError:
                entradas = []
            h01 = [e for e in entradas if "_01H_" in e["name"]]
            plazos = sorted(int(e["name"][-6:-3]) for e in h01)
            subidas = [e.get("LastModified") for e in h01 if e.get("LastModified")]
            tipos = sorted({e["name"].split("/")[-1].split("_")[1] for e in entradas})
            ciclos.append(
                {
                    "init": init,
                    "prefijo": prefijo,
                    "n01": len(h01),
                    "plazo_min": plazos[0] if plazos else None,
                    "plazo_max": plazos[-1] if plazos else None,
                    "primera_subida": min(subidas) if subidas else None,
                    "ultima_subida": max(subidas) if subidas else None,
                    "tipos": tipos,
                    "tamanos_mb": sorted(round(e["size"] / 1e6, 1) for e in h01)[:: max(1, len(h01) // 4)] if h01 else [],
                }
            )
    r(f"Consulta hecha a las {ahora:%Y-%m-%d %H:%M} UTC.")
    r()
    r("| Ciclo (UTC) | Archivos 01H | Plazos | Primera subida | Última subida | Demora (h) | Tipos |")
    r("|---|---|---|---|---|---|---|")
    for c in ciclos:
        demora = (
            f"{(c['ultima_subida'] - c['init']).total_seconds() / 3600:.1f}" if c["ultima_subida"] else "—"
        )
        r(
            f"| {c['init']:%Y-%m-%d %H} | {c['n01']} | {c['plazo_min']}–{c['plazo_max']} | "
            f"{c['primera_subida']:%H:%M} | {c['ultima_subida']:%H:%M} | {demora} | {', '.join(c['tipos'])} |"
            if c["n01"]
            else f"| {c['init']:%Y-%m-%d %H} | 0 | — | — | — | — | — |"
        )
    r()
    completos = [c for c in ciclos if c["n01"] and c["plazo_max"] is not None and c["plazo_max"] >= 72]
    if not completos:
        r("**No hay ciclos completos en las últimas 48 h.**")
        return
    elegido = completos[0]
    r(f"Ciclo completo más reciente: **{elegido['init']:%Y-%m-%d %H} UTC**.")
    r()
    nombre = f"WRFDETAR_01H_{elegido['init']:%Y%m%d}_{elegido['init']:%H}_012.nc"
    ruta = elegido["prefijo"] + nombre
    t0 = time.time()
    crudo = fs.open(ruta, block_size=2**18, cache_type="none")
    contador = Contador(crudo)
    ds = xr.open_dataset(contador, engine="h5netcdf")
    lat = ds["lat"].values
    lon = ds["lon"].values
    bytes_meta = contador.bytes
    t_meta = time.time() - t0
    r(f"Archivo de muestra: `{ruta}` ({fs.size(ruta) / 1e6:.1f} MB).")
    r()
    r(f"- Dimensiones: `{dict(ds.sizes)}`; coordenadas: `{list(ds.coords)}`")
    r(f"- Tiempo válido del archivo: `{str(ds['time'].values[0])[:19]}` (init + 12 h)")
    r(f"- Atributos globales: initial_condition=`{ds.attrs.get('initial_condition')}`, START_DATE=`{ds.attrs.get('START_DATE')}`")
    r()
    r("| Variable | Unidad | long_name | Chunks | Compresión |")
    r("|---|---|---|---|---|")
    for v in ("T2", "HR2", "magViento10", "dirViento10", "PP"):
        if v in ds:
            enc = ds[v].encoding
            r(
                f"| `{v}` | {ds[v].attrs.get('units')} | {ds[v].attrs.get('long_name')} | "
                f"{enc.get('chunksizes')} | zlib={enc.get('zlib')} shuffle={enc.get('shuffle')} |"
            )
        else:
            r(f"| `{v}` | **NO ENCONTRADA** | | | |")
    otras = sorted(set(ds.data_vars) - {"T2", "HR2", "magViento10", "dirViento10", "PP"})
    r()
    r(f"Otras variables del archivo: {', '.join(f'`{o}`' for o in otras)}")
    r()
    R = 6371.0
    la1, lo1 = np.radians(LAT), np.radians(LON)
    la2, lo2 = np.radians(lat.astype("f8")), np.radians(lon.astype("f8"))
    d = 2 * R * np.arcsin(
        np.sqrt(np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2)
    )
    iy, ix = (int(i) for i in np.unravel_index(np.argmin(d), d.shape))
    r(
        f"Punto de grilla más cercano: **(iy={iy}, ix={ix})**, lat={lat[iy, ix]:.5f}, lon={lon[iy, ix]:.5f}, "
        f"distancia **{d[iy, ix]:.2f} km**. Lectura de metadatos + lat/lon 2D: {bytes_meta / 1e6:.2f} MB en {t_meta:.1f} s."
    )
    r()
    ds.close()

    r("Bytes descargados al leer **un solo punto** (`isel(y=iy, x=ix)`):")
    r()
    r("| Archivo | Variables | MB leídos | Segundos | Valores en el punto |")
    r("|---|---|---|---|---|")
    for plazo, variables in (("012", ["T2", "HR2", "magViento10", "dirViento10", "PP"]), ("013", ["PP"])):
        ruta_p = elegido["prefijo"] + f"WRFDETAR_01H_{elegido['init']:%Y%m%d}_{elegido['init']:%H}_{plazo}.nc"
        t0 = time.time()
        contador = Contador(fs.open(ruta_p, block_size=2**18, cache_type="none"))
        ds = xr.open_dataset(contador, engine="h5netcdf")
        pt = ds[variables].isel(y=iy, x=ix).load()
        valores = {k: round(float(pt[k].values.squeeze()), 2) for k in variables}
        r(f"| {plazo} | {len(variables)} | {contador.bytes / 1e6:.1f} | {time.time() - t0:.1f} | `{valores}` |")
        ds.close()
    r()
    r("Semántica de `PP` (¿horaria o acumulada desde el inicio?) con campos completos:")
    r()
    import h5py

    def campo(ruta_c: str, var: str = "PP"):
        with fs.open(ruta_c, block_size=2**22) as f:
            h = h5py.File(f, "r")
            datos = h[var][:]
            tiempos = h["time"][:]
            h.close()
        return tiempos, datos

    pref = elegido["prefijo"]
    base_n = f"{elegido['init']:%Y%m%d}_{elegido['init']:%H}"
    _, a = campo(pref + f"WRFDETAR_01H_{base_n}_011.nc")
    _, b = campo(pref + f"WRFDETAR_01H_{base_n}_012.nc")
    bajan = int(np.sum((a[0] > 0.5) & (b[0] < a[0] - 0.05)))
    r(
        f"- Puntos con PP(011) > 0,5 mm donde PP(012) es menor: **{bajan}** "
        f"→ {'PP no es acumulada desde el inicio (es por intervalo)' if bajan else 'PP podría ser acumulada desde el inicio'}."
    )
    try:
        t10a, m011 = campo(pref + f"WRFDETAR_10M_{base_n}_011.nc")
        t10b, m012 = campo(pref + f"WRFDETAR_10M_{base_n}_012.nc")
        mascara = b[0] > 1.0
        hip_a = m011[1:].sum(0) + m012[0]
        hip_b = m011.sum(0)
        err_a = float(np.abs(hip_a[mascara] - b[0][mascara]).mean()) if mascara.any() else float("nan")
        err_b = float(np.abs(hip_b[mascara] - b[0][mascara]).mean()) if mascara.any() else float("nan")
        r(f"- Archivos 10M: tiempos de `_011` = {list(np.round(t10a, 3))} h desde init.")
        r(
            f"- Contraste con PP 10 min sobre {int(mascara.sum())} puntos con lluvia: "
            f"suma de (t−1h, t] → error medio {err_a:.2e} mm; suma de [t−1h, t) → {err_b:.2e} mm."
        )
        r("  → El `PP` del archivo válido en `t` es la lluvia del intervalo **(t−1h, t]** (hora que termina).")
    except Exception as e:  # pragma: no cover - diagnóstico
        r(f"- Contraste con archivos 10M no disponible: {e}")
    r()


# --------------------------------------------------------------------------
# B — MET Norway Locationforecast 2.0
# --------------------------------------------------------------------------


def verificar_metno(r: Reporte, fixtures: Path) -> None:
    import httpx

    r("## B — MET Norway Locationforecast 2.0 (compact)")
    r()
    params = {"lat": f"{round(LAT, 4):.4f}", "lon": f"{round(LON, 4):.4f}"}
    r(f"User-Agent usado: `{ua()}` · parámetros: `{params}`")
    r()
    t0 = time.time()
    resp = httpx.get(METNO_URL, params=params, headers={"User-Agent": ua()}, timeout=30, follow_redirects=True)
    r(f"- HTTP **{resp.status_code}** en {time.time() - t0:.1f} s, {len(resp.content)} bytes (descomprimidos).")
    cabeceras = {k: resp.headers.get(k) for k in ("content-type", "content-encoding", "expires", "last-modified", "age", "date", "server")}
    r(f"- Cabeceras: `{cabeceras}`")
    if resp.status_code != 200:
        r(f"- Cuerpo (inicio): `{resp.text[:300]!r}`")
        return
    datos = resp.json()
    (fixtures / "metno_compact.json").write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    (fixtures / "metno_headers.json").write_text(json.dumps(cabeceras, indent=1), encoding="utf-8")
    meta = datos["properties"]["meta"]
    serie = datos["properties"]["timeseries"]
    r(f"- `meta.updated_at`: `{meta.get('updated_at')}` · unidades: `{meta.get('units')}`")
    r(f"- `geometry.coordinates`: `{datos.get('geometry', {}).get('coordinates')}`")
    r(f"- Pasos en `timeseries`: {len(serie)} (desde `{serie[0]['time']}` hasta `{serie[-1]['time']}`)")
    con_1h = [p for p in serie if "next_1_hours" in p["data"]]
    r(f"- Pasos con `next_1_hours`: {len(con_1h)} (último: `{con_1h[-1]['time'] if con_1h else '—'}`)")
    pasos = [
        (datetime.fromisoformat(serie[i + 1]["time"].replace("Z", "+00:00")) - datetime.fromisoformat(serie[i]["time"].replace("Z", "+00:00")))
        for i in range(len(serie) - 1)
    ]
    cambio = next((serie[i]["time"] for i, p in enumerate(pasos) if p != timedelta(hours=1)), None)
    r(f"- Primer paso que deja de ser horario: `{cambio}`")
    claves_inst = sorted({k for p in serie for k in p["data"]["instant"]["details"]})
    claves_1h = sorted({k for p in con_1h for k in p["data"]["next_1_hours"].get("details", {})})
    r(f"- Claves `instant.details`: `{claves_inst}`")
    r(f"- Claves `next_1_hours.details`: `{claves_1h}`")
    texto = json.dumps(datos)
    for clave in ("probability_of_precipitation", "wind_speed_of_gust"):
        r(f"- ¿Aparece `{clave}`? **{'sí' if clave in texto else 'no'}**")
    r()
    r("Ejemplo concreto (convención de intervalos):")
    r()
    muestra = [{"time": p["time"], "instant": p["data"]["instant"]["details"], "next_1_hours": p["data"].get("next_1_hours")} for p in serie[:2]]
    r.bloque(json.dumps(muestra, ensure_ascii=False, indent=1), "json")
    r("→ `next_1_hours.precipitation_amount` en `time=t` es la lluvia de **[t, t+1h)** (hora que empieza).")
    r()
    lm = resp.headers.get("last-modified")
    if lm:
        t0 = time.time()
        r2 = httpx.get(
            METNO_URL,
            params=params,
            headers={"User-Agent": ua(), "If-Modified-Since": lm},
            timeout=30,
            follow_redirects=True,
        )
        r(f"- Repetición con `If-Modified-Since: {lm}` → HTTP **{r2.status_code}** ({len(r2.content)} bytes, {time.time() - t0:.1f} s), Expires=`{r2.headers.get('expires')}`")
    r()


# --------------------------------------------------------------------------
# C — Alertas SMN (CAP)
# --------------------------------------------------------------------------


def _parece_challenge(resp) -> bool:
    cuerpo = resp.text[:4000].lower()
    return (
        resp.status_code in (403, 429, 503)
        or "cf-chl" in cuerpo
        or "just a moment" in cuerpo
        or "challenge-platform" in cuerpo
        or "attention required" in cuerpo
    )


def verificar_smn_cap(r: Reporte, fixtures: Path) -> None:
    import httpx
    from defusedxml import ElementTree as ET
    from shapely.geometry import Point, Polygon

    r("## C — Alertas SMN (CAP)")
    r()
    t0 = time.time()
    resp = httpx.get(CAP_FEED, headers={"User-Agent": ua()}, timeout=30, follow_redirects=True)
    cabeceras = {k: resp.headers.get(k) for k in ("content-type", "server", "cf-ray", "date", "last-modified")}
    r(f"- Feed `{CAP_FEED}` → HTTP **{resp.status_code}** en {time.time() - t0:.1f} s, {len(resp.content)} bytes, url final `{resp.url}`")
    r(f"- Cabeceras: `{cabeceras}`")
    if _parece_challenge(resp):
        r("- **Bloqueo / challenge anti-bot detectado** → la fuente se deshabilita en esta ejecución (no se evade).")
        r(f"- Cuerpo (inicio): `{resp.text[:300]!r}`")
        return
    (fixtures / "smn_cap_feed.xml").write_bytes(resp.content)
    raiz = ET.fromstring(resp.content)
    r(f"- Raíz: `{raiz.tag}`")
    items = raiz.findall(".//item")
    r(f"- Ítems en el feed: **{len(items)}**")
    if items:
        primero = items[0]
        r("- Estructura del primer ítem:")
        r.bloque("\n".join(f"{h.tag}: {(h.text or '').strip()[:160]}" for h in primero), "text")
    punto = Point(LON, LAT)
    guardados = 0
    for i, item in enumerate(items[:15]):
        enlace = (item.findtext("link") or "").strip()
        if not enlace:
            continue
        t0 = time.time()
        rc = httpx.get(enlace, headers={"User-Agent": ua()}, timeout=30, follow_redirects=True)
        if _parece_challenge(rc) or rc.status_code != 200:
            r(f"- CAP `{enlace}` → HTTP {rc.status_code} (bloqueo o error)")
            continue
        try:
            alerta = ET.fromstring(rc.content)
        except Exception as e:
            r(f"- CAP `{enlace}` → XML inválido: {e}")
            continue
        infos = alerta.findall("cap:info", CAP_NS)
        contiene = False
        resumen_areas = []
        for info in infos:
            for area in info.findall("cap:area", CAP_NS):
                poligonos = area.findall("cap:polygon", CAP_NS)
                for pol in poligonos:
                    pares = [tuple(float(v) for v in par.split(",")) for par in (pol.text or "").split()]
                    if len(pares) >= 3 and Polygon([(lon_, lat_) for lat_, lon_ in pares]).contains(punto):
                        contiene = True
                resumen_areas.append(f"{area.findtext('cap:areaDesc', default='', namespaces=CAP_NS)[:60]} ({len(poligonos)} polígonos)")
        info0 = infos[0] if infos else None
        if info0 is not None:
            campos = {
                c: (info0.findtext(f"cap:{c}", default="", namespaces=CAP_NS) or "")[:120]
                for c in ("event", "severity", "urgency", "certainty", "onset", "effective", "expires", "headline", "senderName")
            }
            r(
                f"- CAP {i + 1} ({time.time() - t0:.1f} s): identifier=`{alerta.findtext('cap:identifier', namespaces=CAP_NS)}` "
                f"sent=`{alerta.findtext('cap:sent', namespaces=CAP_NS)}` infos={len(infos)} "
                f"campos=`{campos}` áreas=`{resumen_areas[:3]}` **contiene el apiario: {'sí' if contiene else 'no'}**"
            )
        if guardados < 3 or contiene:
            (fixtures / f"smn_cap_alerta_{i + 1:02d}.xml").write_bytes(rc.content)
            guardados += 1
    r()


# --------------------------------------------------------------------------
# D — Open-Meteo (solo con autorización)
# --------------------------------------------------------------------------


def verificar_open_meteo(r: Reporte, fixtures: Path, autorizada: bool) -> None:
    import httpx

    r("## D — Open-Meteo")
    r()
    if not autorizada:
        r("No consultada: el usuario indicó dejarla **apagada** (uso que no califica como no comercial). Sin datos de verificación.")
        r()
        return
    ahora = datetime.now(UTC) + timedelta(hours=-3)
    params = {
        "latitude": f"{round(LAT, 4):.4f}",
        "longitude": f"{round(LON, 4):.4f}",
        "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,wind_speed_10m,wind_direction_10m,wind_gusts_10m",
        "timezone": "America/Argentina/Buenos_Aires",
        "wind_speed_unit": "kmh",
        "start_hour": (ahora + timedelta(hours=1)).strftime("%Y-%m-%dT%H:00"),
        "end_hour": (ahora + timedelta(hours=6)).strftime("%Y-%m-%dT%H:00"),
    }
    resp = httpx.get(OPEN_METEO_URL, params=params, timeout=30)
    r(f"- HTTP **{resp.status_code}**")
    if resp.status_code == 200:
        (fixtures / "open_meteo.json").write_text(json.dumps(resp.json(), ensure_ascii=False, indent=1), encoding="utf-8")
        r.bloque(json.dumps(resp.json().get("hourly_units"), indent=1), "json")
    r()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fuentes", default="smn_wrf,metno,smn_cap")
    ap.add_argument("--open-meteo", action="store_true", help="consultar Open-Meteo (requiere autorización del usuario)")
    ap.add_argument("--docs", default=str(BASE / "docs" / "verificacion_fuentes_ejecucion.md"))
    ap.add_argument("--fixtures", default=str(BASE / "tests" / "fixtures"))
    args = ap.parse_args()

    fixtures = Path(args.fixtures)
    fixtures.mkdir(parents=True, exist_ok=True)
    r = Reporte()
    r("# Verificación de fuentes — ejecución automática")
    r()
    entorno = "GitHub Actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local"
    r(
        f"Generado el {datetime.now(UTC):%Y-%m-%d %H:%M} UTC en **{entorno}** "
        f"({platform.system()} {platform.release()}, Python {platform.python_version()}). "
        f"Coordenada: {LAT}, {LON}."
    )
    r()
    fuentes = [f.strip() for f in args.fuentes.split(",") if f.strip()]
    estado = {}
    for fuente in fuentes:
        try:
            if fuente == "smn_wrf":
                verificar_smn_wrf(r)
            elif fuente == "metno":
                verificar_metno(r, fixtures)
            elif fuente == "smn_cap":
                verificar_smn_cap(r, fixtures)
            else:
                r(f"Fuente desconocida: {fuente}")
                continue
            estado[fuente] = "ok"
        except Exception as e:
            estado[fuente] = f"error: {type(e).__name__}: {e}"
            r(f"**Error verificando `{fuente}`:** `{type(e).__name__}: {e}`")
            r.bloque(traceback.format_exc()[-2000:], "text")
            r()
    verificar_open_meteo(r, fixtures, args.open_meteo)
    r("## Resumen")
    r()
    for fuente, est in estado.items():
        r(f"- `{fuente}`: {est}")
    Path(args.docs).parent.mkdir(parents=True, exist_ok=True)
    Path(args.docs).write_text(r.texto(), encoding="utf-8")
    resumen = os.environ.get("GITHUB_STEP_SUMMARY")
    if resumen:
        with open(resumen, "a", encoding="utf-8") as f:
            f.write(r.texto())
    return 0


if __name__ == "__main__":
    sys.exit(main())
