import httpx
import pytest
import respx

from interfaz4.config import AjustesReintentos
from interfaz4.fuentes.http import ClienteHTTP
from interfaz4.fuentes.open_meteo import URL, FuenteOpenMeteo
from interfaz4.modelos import Apiario
from tests.conftest import local

APIARIO = Apiario(id="produccion_miel", nombre="P", lat=-34.889180362505506, lon=-57.82789829443907)


def respuesta():
    horas = [f"2026-10-10T{h:02d}:00" for h in range(9, 14)]
    n = len(horas)
    return {
        "hourly": {
            "time": horas,
            "temperature_2m": [14.0 + i for i in range(n)],
            "relative_humidity_2m": [80 - i for i in range(n)],
            "precipitation_probability": [10 * i for i in range(n)],
            "precipitation": [0.1 * i for i in range(n)],
            "wind_speed_10m": [12.0 + i for i in range(n)],
            "wind_direction_10m": [135] * n,
            "wind_gusts_10m": [20.0 + i for i in range(n)],
        }
    }


@respx.mock
def test_parametros_y_alineacion_hora_anterior():
    ruta = respx.get(URL).mock(return_value=httpx.Response(200, json=respuesta()))
    f = FuenteOpenMeteo(ClienteHTTP(AjustesReintentos(), dormir=lambda s: None))
    serie = f.obtener(APIARIO, local("2026-10-10T09:00"), local("2026-10-10T13:00"))
    params = ruta.calls.last.request.url.params
    assert params["latitude"] == "-34.8892" and params["longitude"] == "-57.8279"
    assert params["timezone"] == "America/Argentina/Buenos_Aires"
    assert params["wind_speed_unit"] == "kmh"
    assert params["start_hour"] == "2026-10-10T09:00" and params["end_hour"] == "2026-10-10T13:00"
    assert "precipitation_probability" in params["hourly"] and "wind_gusts_10m" in params["hourly"]
    p = serie.puntos
    assert [x.temp_c for x in p] == [14, 15, 16, 17]  # instantáneo en H
    # precipitación, probabilidad y ráfaga en t son de (t−1h, t] → fila H usa H+1
    assert [x.precip_mm for x in p] == pytest.approx([0.1, 0.2, 0.3, 0.4])
    assert [x.prob_precip_pct for x in p] == [10, 20, 30, 40]
    assert [x.rafaga_kmh for x in p] == [21, 22, 23, 24]
    assert p[0].viento_kmh == 12 and p[0].viento_dir_cardinal == "SE"


@respx.mock
def test_error_http_degrada():
    respx.get(URL).mock(return_value=httpx.Response(400, json={"error": True}))
    f = FuenteOpenMeteo(ClienteHTTP(AjustesReintentos(), dormir=lambda s: None))
    serie = f.obtener(APIARIO, local("2026-10-10T09:00"), local("2026-10-10T11:00"))
    assert serie.errores and all(x.temp_c is None for x in serie.puntos)
