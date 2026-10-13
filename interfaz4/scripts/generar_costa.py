"""Genera assets/costa_rdp.geojson con el litoral Natural Earth 10m recortado.

Dominio público. Se corre una sola vez y se commitea el resultado: el motor
en producción ya no descarga nada. Ejecutar desde `interfaz4/`:

    uv run python scripts/generar_costa.py
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen

URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_coastline.geojson"
CAJA = {"lat_min": -36.0, "lat_max": -33.8, "lon_min": -59.2, "lon_max": -56.4}
DESTINO = Path(__file__).resolve().parent.parent / "assets" / "costa_rdp.geojson"


def dentro(lon: float, lat: float) -> bool:
    return CAJA["lon_min"] <= lon <= CAJA["lon_max"] and CAJA["lat_min"] <= lat <= CAJA["lat_max"]


def recortar(coords: list) -> list[list]:
    """Divide un tramo cuando sale de la caja; devuelve tramos de ≥ 2 puntos."""
    tramos: list[list] = []
    actual: list = []
    for lon, lat in coords:
        if dentro(lon, lat):
            actual.append([lon, lat])
        elif len(actual) >= 2:
            tramos.append(actual)
            actual = []
        else:
            actual = []
    if len(actual) >= 2:
        tramos.append(actual)
    return tramos


def main() -> None:
    with urlopen(URL, timeout=30) as resp:  # noqa: S310 - fuente pública
        datos = json.load(resp)
    features: list[dict] = []
    for feature in datos.get("features", []):
        geom = feature.get("geometry") or {}
        tipo = geom.get("type")
        coords = geom.get("coordinates") or []
        tramos: list = []
        if tipo == "LineString":
            tramos = recortar(coords)
        elif tipo == "MultiLineString":
            for trozo in coords:
                tramos.extend(recortar(trozo))
        for tramo in tramos:
            features.append({"type": "Feature", "properties": {}, "geometry": {"type": "LineString", "coordinates": tramo}})
    salida = {"type": "FeatureCollection", "features": features}
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(json.dumps(salida, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Guardado {DESTINO.relative_to(DESTINO.parent.parent)} con {len(features)} tramos")


if __name__ == "__main__":
    main()
