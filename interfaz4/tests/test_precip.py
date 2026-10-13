"""Tests focalizados de precipitación (v1.1): clave única de hora, saneamiento,
formato con `<0,1` y `s/d`, convenciones de intervalo por fuente, y strictness
de modelos y plantillas."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pytest
import xarray as xr
from jinja2 import Environment, PackageLoader, StrictUndefined

from interfaz4 import normalizar, tiempo
from interfaz4.fuentes.metno import URL as URL_METNO
from interfaz4.fuentes.metno import CacheMetno, FuenteMETNorway
from interfaz4.fuentes.smn_wrf import FuenteSMNWRF, RepositorioWRF
from interfaz4.informe.constructor import fmt_precip
from interfaz4.modelos import Apiario, PuntoHorario
from tests.conftest import local


# ------------------------------------------------------------------ fmt_precip


def test_fmt_precip_distingue_sin_dato_cero_y_subumbral():
    assert fmt_precip(None) == "s/d"
    assert fmt_precip(0) == "0,0"
    assert fmt_precip(0.0) == "0,0"
    assert fmt_precip(0.04) == "<0,1"
    assert fmt_precip(0.099) == "<0,1"
    assert fmt_precip(0.1) == "0,1"
    assert fmt_precip(2.35) in ("2,3", "2,4")  # bankers' rounding es-AR
    assert fmt_precip(1234.5) == "1234,5"


# -------------------------------------------------------------- clave_hora


def test_clave_hora_normaliza_a_hora_argentina():
    utc = datetime(2026, 10, 7, 15, 0, tzinfo=UTC)
    assert tiempo.clave_hora(utc) == local("2026-10-07T12:00")
    assert tiempo.clave_hora(local("2026-10-07T12:34")) == local("2026-10-07T12:00")


def test_clave_hora_rechaza_naive():
    with pytest.raises(ValueError):
        tiempo.clave_hora(datetime(2026, 10, 7, 12, 0))


# --------------------------------------------------------------- modelo


def test_punto_horario_rechaza_campos_desconocidos():
    """`extra='forbid'`: un nombre mal escrito (p. ej. precipitacion_mm en
    lugar de precip_mm) falla fuerte en vez de perderse como 0,0."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        PuntoHorario(hora_local=local("2026-10-07T09:00"), precipitacion_mm=1.3)  # type: ignore[call-arg]


# --------------------------------------------------------------- plantilla


def test_plantilla_estricta_con_atributo_inexistente():
    env = Environment(
        loader=PackageLoader("interfaz4", "informe/plantillas"), undefined=StrictUndefined, autoescape=False
    )
    plantilla = env.from_string("{{ obj.inexistente }}")
    with pytest.raises(Exception):
        plantilla.render(obj=object())


# --------------------------------------------------------------- saneamiento


def test_lluvia_sanitiza_negativos_pero_distingue_none():
    assert normalizar.lluvia(None) is None
    assert normalizar.lluvia("x") is None
    assert normalizar.lluvia(-1e-8) == 0.0  # ruido numérico del WRF
    assert normalizar.lluvia(0.123) == pytest.approx(0.123)
    assert normalizar.lluvia(float("nan")) is None


# --------------------------------------------------------- convenciones


def test_wrf_fila_h_toma_archivo_valido_en_h_mas_1(tmp_path):
    """Convención WRF: la lluvia de la fila 11:00 local sale del archivo
    cuyo valid-time es 12:00 local (= 15:00 UTC = plazo 003 del ciclo 12 UTC)."""
    import fsspec

    _escribir_wrf(tmp_path, init_utc=datetime(2026, 10, 12, 12, tzinfo=UTC), plazo=3, pp=1.3)
    _escribir_wrf(tmp_path, init_utc=datetime(2026, 10, 12, 12, tzinfo=UTC), plazo=2, pp=0.0)
    _escribir_wrf(tmp_path, init_utc=datetime(2026, 10, 12, 12, tzinfo=UTC), plazo=4, pp=0.0)
    repo = RepositorioWRF(fs=fsspec.filesystem("file"), raiz=str(tmp_path))
    reloj = lambda: datetime(2026, 10, 12, 14, 0, tzinfo=UTC)  # noqa: E731
    fuente = FuenteSMNWRF(repo, reloj=reloj)
    apiario = Apiario(id="t", nombre="t", lat=-34.9, lon=-57.8)
    serie = fuente.obtener(apiario, local("2026-10-12T10:00"), local("2026-10-12T13:00"), variables="precipitacion")
    por_hora = {p.hora_local.strftime("%H"): p.precip_mm for p in serie.puntos}
    assert por_hora == {"10": 0.0, "11": 1.3, "12": 0.0}  # fila 11 = archivo H+1 = 12 local


def test_metno_fila_h_toma_timestamp_h():
    """MET Norway: `next_1_hours` en time=H representa [H, H+1h) → fila H."""
    import httpx

    cache = CacheMetno(None)
    cuerpo = {
        "properties": {
            "meta": {"updated_at": "2026-10-12T12:00:00Z"},
            "timeseries": [
                {
                    "time": "2026-10-12T12:00:00Z",  # = 09:00 local
                    "data": {
                        "instant": {"details": {"air_temperature": 20.0}},
                        "next_1_hours": {"details": {"precipitation_amount": 2.1}},
                    },
                },
                {
                    "time": "2026-10-12T13:00:00Z",  # = 10:00 local
                    "data": {
                        "instant": {"details": {"air_temperature": 21.0}},
                        "next_1_hours": {"details": {"precipitation_amount": 0.0}},
                    },
                },
            ],
        }
    }
    cache.guardar("https://api.met.no/weatherapi/locationforecast/2.0/compact?lat=-34.8892&lon=-57.8279",
                  {"last_modified": None, "expires": "2100-01-01T00:00:00+00:00", "cuerpo": cuerpo})
    from interfaz4.config import AjustesReintentos
    from interfaz4.fuentes.http import ClienteHTTP

    http = ClienteHTTP(
        AjustesReintentos(http_intentos=1),
        transport=httpx.MockTransport(lambda r: (_ for _ in ()).throw(AssertionError(f"sin red: {r.url}"))),
        dormir=lambda s: None,
    )
    reloj = lambda: datetime(2026, 10, 12, 11, 0, tzinfo=UTC)  # noqa: E731
    fuente = FuenteMETNorway(http, cache, reloj=reloj)
    apiario = Apiario(id="t", nombre="t", lat=-34.8892, lon=-57.8279)
    serie = fuente.obtener(apiario, local("2026-10-12T09:00"), local("2026-10-12T11:00"))
    assert [(p.hora_local.strftime("%H"), p.precip_mm) for p in serie.puntos] == [("09", 2.1), ("10", 0.0)]


# ----------------------------------------------------------- punta a punta


def test_wrf_valor_crudo_llega_al_informe(tmp_path):
    """1,3 mm en el crudo aparece como 1,3 en la fila correcta del render."""
    import fsspec
    from interfaz4.informe.constructor import generar
    from interfaz4.informe.recoleccion import DatosInforme

    _escribir_wrf(tmp_path, init_utc=datetime(2026, 10, 12, 12, tzinfo=UTC), plazo=3, pp=1.3)
    _escribir_wrf(tmp_path, init_utc=datetime(2026, 10, 12, 12, tzinfo=UTC), plazo=2, pp=0.0)
    _escribir_wrf(tmp_path, init_utc=datetime(2026, 10, 12, 12, tzinfo=UTC), plazo=4, pp=0.0)
    reloj = lambda: datetime(2026, 10, 12, 14, 0, tzinfo=UTC)  # noqa: E731
    repo = RepositorioWRF(fs=fsspec.filesystem("file"), raiz=str(tmp_path))
    apiario = Apiario(id="t", nombre="Prueba", lat=-34.9, lon=-57.8)
    visita = _visita_prueba()
    serie = FuenteSMNWRF(repo, reloj=reloj).obtener(
        apiario, local("2026-10-12T10:00"), local("2026-10-12T13:00"), variables="todas"
    )
    datos = DatosInforme(
        visita=visita, apiario=apiario, hito=24, generado=reloj(),
        series=[serie], fuentes_deshabilitadas=["open_meteo", "ecmwf_ens"],
    )
    render = generar(datos, comparar_24_12=False)
    assert "1,3" in render.texto  # fila 11:00 con el valor crudo


# -------------------------------------------------------------- helpers


def _escribir_wrf(carpeta, init_utc: datetime, plazo: int, pp: float):
    ny = nx = 5
    lat = np.linspace(-35.0, -34.8, ny).reshape(ny, 1).repeat(nx, 1)
    lon = np.linspace(-57.9, -57.7, nx).reshape(1, nx).repeat(ny, 0)
    pp_g = np.zeros((1, ny, nx), dtype="f4")
    pp_g[0, 2, 2] = pp  # el centro corresponde al apiario de prueba
    ds = xr.Dataset(
        {
            "T2": (("time", "y", "x"), np.full((1, ny, nx), 20.0, "f4")),
            "HR2": (("time", "y", "x"), np.full((1, ny, nx), 70.0, "f4")),
            "magViento10": (("time", "y", "x"), np.full((1, ny, nx), 3.0, "f4")),
            "dirViento10": (("time", "y", "x"), np.full((1, ny, nx), 90.0, "f4")),
            "PP": (("time", "y", "x"), pp_g),
        },
        coords={
            "lat": (("y", "x"), lat),
            "lon": (("y", "x"), lon),
            "time": ("time", np.array([plazo], dtype="f8")),
        },
    )
    ds["time"].attrs["units"] = f"hours since {init_utc:%Y-%m-%dT%H:%M:%S}"
    ds["PP"].attrs["_FillValue"] = np.float32(1e20)
    carpeta_ciclo = carpeta / "DATA/WRF/DET" / f"{init_utc:%Y/%m/%d}" / f"{init_utc:%H}"
    carpeta_ciclo.mkdir(parents=True, exist_ok=True)
    archivo = carpeta_ciclo / f"WRFDETAR_01H_{init_utc:%Y%m%d}_{init_utc:%H}_{plazo:03d}.nc"
    ds.to_netcdf(archivo, engine="h5netcdf")
    return archivo


def _visita_prueba():
    from interfaz4.modelos import Visita

    return Visita(
        id="2026-10-12-t-01",
        apiario="t",
        fecha="2026-10-12",  # type: ignore[arg-type]
        desde="10:00",  # type: ignore[arg-type]
        hasta="13:00",  # type: ignore[arg-type]
        responsable="Prueba",
    )
