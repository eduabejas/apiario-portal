"""Mapa de lluvia acumulada WRF-SMN alrededor del apiario (v1.1).

Decisión de diseño: usamos el mismo campo `PP` del WRF que ya leemos para
el detalle horario. Sin fuentes ni licencias nuevas; nada de scraping del
sitio del SMN. La barra de colores es una leyenda cuantitativa (mm), no
un semáforo valorativo: compatible con la regla de no interpretar.
"""

from __future__ import annotations

import io
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

# Escala en mm: < 0,1 queda transparente (sobre fondo claro = "sin lluvia visible").
NIVELES = (0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 1000.0)
COLORES = (
    "#a6e3ff",  # 0,1 - 0,5
    "#3fa9f5",  # 0,5 - 1
    "#1f5fd1",  # 1 - 2
    "#2fbf4a",  # 2 - 5
    "#f5e43a",  # 5 - 10
    "#f59a23",  # 10 - 20
    "#e53935",  # 20 - 50
    "#b0179e",  # 50+
)


@dataclass(frozen=True)
class ResultadoMapa:
    png: bytes
    maximo_mm: float
    horas: int


def cargar_costa(ruta: Path) -> list[tuple[list[float], list[float]]]:
    """Litoral recortado (GeoJSON Natural Earth 10m) como pares (lon, lat)."""
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    segmentos: list[tuple[list[float], list[float]]] = []
    for feature in datos.get("features", []):
        geom = feature.get("geometry") or {}
        tipo = geom.get("type")
        coords = geom.get("coordinates") or []
        tramos = [coords] if tipo == "LineString" else coords if tipo == "MultiLineString" else []
        for tramo in tramos:
            xs, ys = zip(*((float(x), float(y)) for x, y in tramo), strict=True)
            segmentos.append((list(xs), list(ys)))
    return segmentos


def render_mapa(
    lat2d: np.ndarray,
    lon2d: np.ndarray,
    pp: np.ndarray,
    lat0: float,
    lon0: float,
    costa: list[tuple[list[float], list[float]]],
    titulo: str,
) -> bytes:
    """PNG inline del campo `pp` sobre la caja. `pp` en mm acumulados."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap

    cmap = ListedColormap(COLORES).with_extremes(under=(1, 1, 1, 0))  # < 0,1 mm → transparente
    norm = BoundaryNorm(NIVELES, cmap.N)

    fig, ax = plt.subplots(figsize=(3.4, 3.7), dpi=110)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#f3f6f9")
    m = ax.pcolormesh(lon2d, lat2d, pp, cmap=cmap, norm=norm, shading="auto")
    for xs, ys in costa:
        ax.plot(xs, ys, lw=0.6, color="#333")
    ax.plot(lon0, lat0, "o", ms=5, mfc="white", mec="black")
    ax.set_xlim(float(lon2d.min()), float(lon2d.max()))
    ax.set_ylim(float(lat2d.min()), float(lat2d.max()))
    ax.set_aspect(1 / float(np.cos(np.radians(lat0))))
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_title(titulo, fontsize=7)

    cb = fig.colorbar(m, ax=ax, orientation="horizontal", fraction=0.05, pad=0.03, ticks=list(NIVELES[:-1]))
    cb.ax.tick_params(labelsize=6)
    cb.set_label("mm", fontsize=6)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()
