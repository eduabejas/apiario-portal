#!/usr/bin/env python3
"""Genera un "mini bucket" WRF-SMN real para tests offline.

Recorta una ventana de (2·m+1)×(2·m+1) puntos alrededor del apiario de los
archivos horarios de un ciclo real y los guarda con la misma ruta, nombres de
variables, forma (time, y, x), unidades de tiempo ("hours since <init>"),
_FillValue y atributos que en s3://smn-ar-wrf. Así el código de producción
los lee con un filesystem local sin cambios.

Uso (desde interfaz4/):
    uv run python scripts/generar_fixture_wrf.py --ciclo 2026-10-03T12 --plazos 0-30
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path

import h5py
import numpy as np
import s3fs

LAT = -34.889180362505506
LON = -57.82789829443907
VARIABLES = ["T2", "HR2", "magViento10", "dirViento10", "PP"]
ATRIBUTOS_INTERNOS = {"DIMENSION_LIST", "REFERENCE_LIST", "_Netcdf4Coordinates", "_Netcdf4Dimid", "CLASS", "NAME"}
BASE = Path(__file__).resolve().parent.parent


def indice_mas_cercano(lat: np.ndarray, lon: np.ndarray) -> tuple[int, int]:
    la1, lo1 = np.radians(LAT), np.radians(LON)
    la2, lo2 = np.radians(lat.astype("f8")), np.radians(lon.astype("f8"))
    d = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    iy, ix = np.unravel_index(np.argmin(d), d.shape)
    return int(iy), int(ix)


def copiar_atributos(origen, destino) -> None:
    for clave, valor in origen.attrs.items():
        if clave not in ATRIBUTOS_INTERNOS:
            destino.attrs[clave] = valor


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ciclo", default="2026-10-03T12")
    ap.add_argument("--plazos", default="0-30")
    ap.add_argument("--margen", type=int, default=4)
    ap.add_argument("--salida", default=str(BASE / "tests" / "fixtures" / "smn_wrf"))
    args = ap.parse_args()

    init = datetime.strptime(args.ciclo, "%Y-%m-%dT%H")
    p0, p1 = (int(x) for x in args.plazos.split("-"))
    fs = s3fs.S3FileSystem(anon=True, client_kwargs={"region_name": "us-west-2"})
    rel = f"DATA/WRF/DET/{init:%Y/%m/%d}/{init:%H}"
    nombre = lambda p: f"WRFDETAR_01H_{init:%Y%m%d}_{init:%H}_{p:03d}.nc"  # noqa: E731

    with fs.open(f"smn-ar-wrf/{rel}/{nombre(p0)}", block_size=2**22) as f, h5py.File(f, "r") as h:
        iy, ix = indice_mas_cercano(h["lat"][...], h["lon"][...])
    m = args.margen
    ys, xs = slice(iy - m, iy + m + 1), slice(ix - m, ix + m + 1)
    print(f"punto (iy={iy}, ix={ix}); recorte y[{ys.start}:{ys.stop}] x[{xs.start}:{xs.stop}]")

    destino = Path(args.salida) / rel
    if destino.exists():
        shutil.rmtree(destino)
    destino.mkdir(parents=True)

    for p in range(p0, p1 + 1):
        with fs.open(f"smn-ar-wrf/{rel}/{nombre(p)}", "rb", block_size=2**18, cache_type="none") as f, h5py.File(f, "r") as src:
            with h5py.File(destino / nombre(p), "w", libver="latest") as dst:
                copiar_atributos(src, dst)
                dst.attrs["fixture"] = (
                    f"Recorte {2 * m + 1}x{2 * m + 1} de {nombre(p)} centrado en (iy={iy}, ix={ix}) "
                    "para tests offline de interfaz4"
                )
                t = dst.create_dataset("time", data=src["time"][...])
                copiar_atributos(src["time"], t)
                for coord in ("lat", "lon"):
                    d = dst.create_dataset(coord, data=src[coord][ys, xs])
                    copiar_atributos(src[coord], d)
                for v in VARIABLES:
                    d = dst.create_dataset(v, data=src[v][:, ys, xs])
                    copiar_atributos(src[v], d)
        print("ok", nombre(p), flush=True)


if __name__ == "__main__":
    main()
