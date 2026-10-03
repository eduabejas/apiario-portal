import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx

from interfaz4.config import AjustesReintentos
from interfaz4.fuentes.http import ClienteHTTP
from interfaz4.fuentes.metno import URL, CacheMetno, FuenteMETNorway
from interfaz4.modelos import Apiario
from tests.conftest import FIXTURES, local

APIARIO = Apiario(id="produccion_miel", nombre="P", lat=-34.889180362505506, lon=-57.82789829443907)
UA = "interfaz4-test/0.1 contacto@example.com"
CUERPO = json.loads((FIXTURES / "metno_compact.json").read_text(encoding="utf-8"))
CABECERAS = json.loads((FIXTURES / "metno_headers.json").read_text(encoding="utf-8"))
# Respuesta real capturada en GitHub Actions el 03/10/2026 21:32 UTC.
AHORA = datetime(2026, 10, 3, 21, 32, 30, tzinfo=UTC)


def fuente(tmp_path=None, reloj=lambda: AHORA, intentos=3):
    http = ClienteHTTP(AjustesReintentos(http_intentos=intentos, timeout_seg=5), user_agent=UA, dormir=lambda s: None)
    cache = CacheMetno(tmp_path / "cache_metno.json" if tmp_path else None)
    return FuenteMETNorway(http, cache, reloj=reloj)


def ok():
    return httpx.Response(
        200,
        json=CUERPO,
        headers={"expires": CABECERAS["expires"], "last-modified": CABECERAS["last-modified"]},
    )


def detalle(t_utc: str):
    for paso in CUERPO["properties"]["timeseries"]:
        if paso["time"] == t_utc:
            return paso["data"]
    raise KeyError(t_utc)


@respx.mock
def test_request_con_user_agent_y_4_decimales():
    ruta = respx.get(URL).mock(return_value=ok())
    fuente().obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T13:00"))
    req = ruta.calls.last.request
    assert req.headers["User-Agent"] == UA
    assert req.url.params["lat"] == "-34.8892" and req.url.params["lon"] == "-57.8279"


@respx.mock
def test_alineacion_hora_que_empieza_y_unidades():
    respx.get(URL).mock(return_value=ok())
    serie = fuente().obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T13:00"))
    assert serie.fuente == "metno" and not serie.errores
    assert [p.hora_local.hour for p in serie.puntos] == [9, 10, 11, 12]
    # 09:00 hora Argentina = 12:00 UTC
    d = detalle("2026-10-04T12:00:00Z")
    p = serie.puntos[0]
    assert p.temp_c == pytest.approx(d["instant"]["details"]["air_temperature"])
    assert p.hr_pct == pytest.approx(d["instant"]["details"]["relative_humidity"])
    assert p.viento_kmh == pytest.approx(d["instant"]["details"]["wind_speed"] * 3.6, abs=0.01)
    assert p.viento_dir_grados == pytest.approx(d["instant"]["details"]["wind_from_direction"], abs=0.05)
    # next_1_hours en t = [t, t+1h): la fila 09 usa el timestamp 12:00Z
    assert p.precip_mm == pytest.approx(d["next_1_hours"]["details"]["precipitation_amount"])
    assert serie.puntos[3].precip_mm == pytest.approx(
        detalle("2026-10-04T15:00:00Z")["next_1_hours"]["details"]["precipitation_amount"]
    )
    # MET Norway no publica ráfagas ni probabilidad para Argentina
    assert all(p.rafaga_kmh is None and p.prob_precip_pct is None for p in serie.puntos)
    assert serie.emitido_utc == datetime(2026, 10, 3, 19, 21, 14, tzinfo=UTC)
    assert serie.detalle_emision == "actualizado 03/10 19:21 UTC"


@respx.mock
def test_pasos_de_6_horas_dejan_lluvia_horaria_en_sd():
    respx.get(URL).mock(return_value=ok())
    # Desde 2026-10-06T12Z la serie es cada 6 h y sin next_1_hours.
    serie = fuente().obtener(APIARIO, local("2026-10-06T09:00"), local("2026-10-06T12:00"))
    assert serie.puntos[0].temp_c is not None  # 12Z existe (instantáneo)
    assert serie.puntos[0].precip_mm is None
    assert serie.puntos[1].temp_c is None  # 13Z no existe


@respx.mock
def test_cache_respeta_expires_y_revalida(tmp_path):
    ruta = respx.get(URL).mock(return_value=ok())
    fuente(tmp_path).obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T10:00"))
    assert ruta.call_count == 1
    # Otra ejecución antes de Expires: no se consulta.
    fuente(tmp_path, reloj=lambda: AHORA + timedelta(minutes=10)).obtener(
        APIARIO, local("2026-10-04T09:00"), local("2026-10-04T10:00")
    )
    assert ruta.call_count == 1
    # Después de Expires: If-Modified-Since → 304 → se reutiliza el cuerpo guardado.
    ruta.mock(return_value=httpx.Response(304, headers={"expires": "Sat, 03 Oct 2026 23:30:00 GMT"}))
    serie = fuente(tmp_path, reloj=lambda: AHORA + timedelta(hours=1)).obtener(
        APIARIO, local("2026-10-04T09:00"), local("2026-10-04T10:00")
    )
    assert ruta.call_count == 2
    assert ruta.calls.last.request.headers["If-Modified-Since"] == CABECERAS["last-modified"]
    assert serie.puntos[0].temp_c is not None and not serie.errores


@respx.mock
def test_misma_coordenada_se_consulta_una_vez_por_ejecucion():
    ruta = respx.get(URL).mock(return_value=ok())
    f = fuente()
    f.obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T10:00"))
    f.obtener(APIARIO.model_copy(update={"id": "otro"}), local("2026-10-05T09:00"), local("2026-10-05T10:00"))
    assert ruta.call_count == 1


@respx.mock
def test_203_agrega_aviso():
    respx.get(URL).mock(return_value=httpx.Response(203, json=CUERPO))
    serie = fuente().obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T10:00"))
    assert serie.puntos[0].temp_c is not None
    assert any("203" in e for e in serie.errores)


@respx.mock
def test_429_frena_sin_reintentar():
    ruta = respx.get(URL).mock(return_value=httpx.Response(429))
    f = fuente()
    serie = f.obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T10:00"))
    assert ruta.call_count == 1
    assert "429" in serie.errores[0]
    assert serie.puntos[0].temp_c is None
    f.obtener(APIARIO.model_copy(update={"lat": -30.0}), local("2026-10-04T09:00"), local("2026-10-04T10:00"))
    assert ruta.call_count == 1  # frenada para el resto de la ejecución


@respx.mock
def test_403_deshabilita():
    respx.get(URL).mock(return_value=httpx.Response(403, text="Forbidden"))
    serie = fuente().obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T10:00"))
    assert "403" in serie.errores[0]
    assert len(serie.puntos) == 1 and serie.puntos[0].temp_c is None


@respx.mock
def test_5xx_reintenta_y_degrada():
    ruta = respx.get(URL).mock(return_value=httpx.Response(500))
    serie = fuente(intentos=3).obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T10:00"))
    assert ruta.call_count == 3
    assert serie.errores and serie.puntos[0].temp_c is None
