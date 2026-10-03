#!/usr/bin/env python3
"""Genera un "mini bucket" WRF-SMN real para tests offline.

Recorta una ventana de (2·m+1)×(2·m+1) puntos alrededor del apiario de los
archivos horarios de un ciclo real y los guarda con la misma ruta, nombres de
variables, dimensiones y atributos que en s3://smn-ar-wrf, de modo que el
código de producción pueda leerlos con un filesystem local.

Uso (desde interfaz4/):
    uv run python scripts/generar_fixture_wrf.py --ciclo 2026-10-03T12 --plazos 0-30
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import s3fs
import xarray as xr

LAT = -34.889180362505506
LON = -57.82789829443907
VARIABLES = ["T2", "HR2", "magViento10", "dirViento10", "PP"]
BASE = Path(__file__).resolve().parent.parent


def indice_mas_cercano(lat: np.ndarray, lon: np.ndarray) -> tuple[int, int]:
    la1, lo1 = np.radians(LAT), np.radians(LON)
    la2, lo2 = np.radians(lat.astype("f8")), np.radians(lon.astype("f8"))
    d = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    iy, ix = np.unravel_index(np.argmin(d), d.shape)
    return int(iy), int(ix)


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

    with fs.open(f"smn-ar-wrf/{rel}/{nombre(p0)}") as f:
        ds = xr.open_dataset(f, engine="h5netcdf")
        iy, ix = indice_mas_cercano(ds["lat"].values, ds["lon"].values)
        ds.close()
    m = args.margen
    print(f"punto (iy={iy}, ix={ix}); recorte y[{iy - m}:{iy + m + 1}] x[{ix - m}:{ix + m + 1}]")

    destino = Path(args.salida) / rel
    destino.mkdir(parents=True, exist_ok=True)

    def recortar(p: int) -> str:
        with fs.open(f"smn-ar-wrf/{rel}/{nombre(p)}", block_size=2**22) as f:
            ds = xr.open_dataset(f, engine="h5netcdf")
            sub = ds[VARIABLES].isel(y=slice(iy - m, iy + m + 1), x=slice(ix - m, ix + m + 1)).load()
            sub.attrs = dict(ds.attrs)
            sub.attrs["fixture"] = f"Recorte de {nombre(p)} centrado en (iy={iy}, ix={ix}) para tests de interfaz4"
            ds.close()
        for v in sub.variables:
            sub[v].encoding = {}
        sub.to_netcdf(destino / nombre(p), engine="h5netcdf")
        return nombre(p)

    with ThreadPoolExecutor(max_workers=6) as pool:
        for hecho in pool.map(recortar, range(p0, p1 + 1)):
            print("ok", hecho)


if __name__ == "__main__":
    main()
