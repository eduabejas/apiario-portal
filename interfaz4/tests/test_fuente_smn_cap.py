from datetime import UTC, datetime

import httpx
import pytest
import respx

from interfaz4.config import AjustesReintentos
from interfaz4.fuentes.http import ClienteHTTP
from interfaz4.fuentes.smn_cap import FEED, FuenteAlertasSMN, parsear_cap, parsear_feed, superpone
from interfaz4.modelos import Apiario
from tests.conftest import FIXTURES, local

APIARIO = Apiario(id="produccion_miel", nombre="P", lat=-34.889180362505506, lon=-57.82789829443907)
REAL_1 = (FIXTURES / "smn_cap_alerta_01.xml").read_bytes()  # aviso real (Formosa), 03/10/2026
SINTETICA = (FIXTURES / "smn_cap_sintetica_berisso.xml").read_bytes()
URL_REAL = "https://ssl.smn.gob.ar/feeds/CAP/avisocortoplazo/2026_10_03_2116_cap_es.xml"
URL_SINT = "https://ssl.smn.gob.ar/feeds/CAP/xml_generados/sintetica_berisso.xml"


def feed(*enlaces: str) -> bytes:
    items = "".join(f"<item><title>T</title><link>{e}</link><guid>{e}</guid></item>" for e in enlaces)
    return f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>{items}</channel></rss>'.encode()


def fuente():
    http = ClienteHTTP(AjustesReintentos(http_intentos=1, timeout_seg=5), user_agent="t/1", dormir=lambda s: None)
    return FuenteAlertasSMN(http, reloj=lambda: datetime(2026, 10, 4, 12, tzinfo=UTC))


def test_feed_real():
    enlaces = parsear_feed((FIXTURES / "smn_cap_feed.xml").read_bytes())
    assert len(enlaces) == 68
    assert enlaces[0] == URL_REAL
    assert all(e.startswith("https://ssl.smn.gob.ar/feeds/CAP/") for e in enlaces)


def test_cap_real_se_copia_textual():
    [ag] = parsear_cap(REAL_1, URL_REAL)
    a = ag.alerta
    assert a.identificador == "urn:oid:2.49.0.1.32.0.2026.10.03.21.16.00"
    assert a.evento == "TORMENTAS FUERTES"
    assert a.severidad == "Severe" and a.urgencia == "Immediate" and a.certeza == "Observed"
    assert a.titular == "AVISO NARANJA POR TORMENTAS FUERTES CON LLUVIAS INTENSAS, RAFAGAS Y CAIDA DE GRANIZO"
    assert a.instruccion.startswith("Retirá o asegurá objetos que puedan ser arrojados por el viento.")
    assert "evitá el uso de teléfonos con cable" in a.instruccion
    assert a.areas == ["FORMOSA: FORMOSA - PIRANE."]
    # Sin onset/effective: la vigencia arranca en sent.
    assert a.inicio is None and a.enviada == local("2026-10-03T21:16")
    assert a.expira == local("2026-10-03T22:16")
    assert len(ag.poligonos) == 1
    assert not ag.contiene(APIARIO.lat, APIARIO.lon)


def test_cap_sintetica_contiene_al_apiario():
    [ag] = parsear_cap(SINTETICA, URL_SINT)
    assert ag.contiene(APIARIO.lat, APIARIO.lon)
    assert ag.alerta.descripcion == (
        "El área será afectada por tormentas de variada intensidad, algunas localmente fuertes.\n"
        "Se esperan valores de precipitación acumulada entre 20 y 50 mm."
    )


@pytest.mark.parametrize(
    "inicio,fin,esperado",
    [
        ("2026-10-04T09:00", "2026-10-04T13:00", True),  # se superpone (onset 10:00)
        ("2026-10-04T07:00", "2026-10-04T10:00", False),  # termina justo cuando empieza
        ("2026-10-04T18:00", "2026-10-04T20:00", False),  # empieza cuando expira
        ("2026-10-04T17:00", "2026-10-04T19:00", True),
        ("2026-10-05T09:00", "2026-10-05T13:00", False),
    ],
)
def test_superposicion_con_la_ventana(inicio, fin, esperado):
    [ag] = parsear_cap(SINTETICA)
    assert superpone(ag.alerta, local(inicio), local(fin)) is esperado


@respx.mock
def test_obtener_filtra_por_punto_y_ventana():
    respx.get(FEED).mock(return_value=httpx.Response(200, content=feed(URL_REAL, URL_SINT)))
    respx.get(URL_REAL).mock(return_value=httpx.Response(200, content=REAL_1))
    respx.get(URL_SINT).mock(return_value=httpx.Response(200, content=SINTETICA))
    f = fuente()
    res = f.obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T13:00"))
    assert res.disponible and not res.errores
    assert [a.identificador for a in res.alertas] == ["urn:oid:2.49.0.1.32.0.2026.10.04.08.00.00"]
    # Otra ventana fuera de la vigencia: sin alertas, sin volver a descargar.
    res2 = f.obtener(APIARIO, local("2026-10-05T09:00"), local("2026-10-05T13:00"))
    assert res2.disponible and res2.alertas == []
    assert respx.calls.call_count == 3


@respx.mock
def test_challenge_deshabilita_sin_evadir():
    ruta = respx.get(FEED).mock(
        return_value=httpx.Response(
            403, text="<html>Attention Required! | Cloudflare</html>", headers={"content-type": "text/html", "server": "cloudflare"}
        )
    )
    res = fuente().obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T13:00"))
    assert not res.disponible
    assert "anti-bot" in res.errores[0] or "403" in res.errores[0]
    assert ruta.call_count == 1


@respx.mock
def test_xml_que_falla_se_informa_y_sigue():
    respx.get(FEED).mock(return_value=httpx.Response(200, content=feed(URL_REAL, URL_SINT)))
    respx.get(URL_REAL).mock(return_value=httpx.Response(404))
    respx.get(URL_SINT).mock(return_value=httpx.Response(200, content=SINTETICA))
    res = fuente().obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T13:00"))
    assert res.disponible and len(res.alertas) == 1
    assert res.errores == ["1 de 2 avisos del feed no se pudieron leer"]


def test_status_no_actual_y_cancel_se_ignoran():
    ejercicio = SINTETICA.replace(b"<cap:status>Actual</cap:status>", b"<cap:status>Exercise</cap:status>")
    cancel = SINTETICA.replace(b"<cap:msgType>Alert</cap:msgType>", b"<cap:msgType>Cancel</cap:msgType>")
    assert parsear_cap(ejercicio) == [] and parsear_cap(cancel) == []


def test_area_con_circulo():
    xml = SINTETICA.replace(
        b"<cap:polygon>-34.80,-57.95 -34.80,-57.70 -35.00,-57.70 -35.00,-57.95 -34.80,-57.95</cap:polygon>",
        b"<cap:circle>-34.92,-57.95 15</cap:circle>",
    )
    [ag] = parsear_cap(xml)
    assert ag.circulos and ag.contiene(APIARIO.lat, APIARIO.lon)
    assert not ag.contiene(-34.0, -57.0)


def test_no_es_cap():
    with pytest.raises(ValueError):
        parsear_cap(b"<rss/>")


def test_alerta_generada_real_namespace_por_defecto():
    """Formato de xml_generados (alertas por zona): namespace por defecto,
    msgType=Update con <references>, areaDesc vacío y entidades XML."""
    [ag] = parsear_cap((FIXTURES / "smn_cap_alerta_generada_nevadas.xml").read_bytes())
    a = ag.alerta
    assert a.identificador == "urn:oid:2.49.0.1.32.0.2026.10.03.20.39.52.8"
    assert a.evento == "Nevadas" and a.severidad == "Moderate"
    assert a.inicio == local("2026-10-03T20:39:52") and a.expira == local("2026-10-04T14:59:59")
    assert a.descripcion.startswith("El área será afectada por nevadas persistentes")
    assert a.areas == []
    assert ag.referencias == ["urn:oid:2.49.0.1.32.0.2026.10.03.08.57.12"]
    assert ag.contiene(-41.5, -71.4)  # dentro del polígono (zona cordillerana de Río Negro)
    assert not ag.contiene(APIARIO.lat, APIARIO.lon)


@respx.mock
def test_alerta_reemplazada_por_update_no_se_muestra():
    original = SINTETICA
    actualizacion = (
        SINTETICA.replace(b"2026.10.04.08.00.00", b"2026.10.04.09.00.00")
        .replace(b"<cap:msgType>Alert</cap:msgType>", b"<cap:msgType>Update</cap:msgType>"
                 b"<cap:references>smn@smn.gov.ar,urn:oid:2.49.0.1.32.0.2026.10.04.08.00.00,2026-10-04T08:00:00-03:00</cap:references>")
    )
    url_upd = "https://ssl.smn.gob.ar/feeds/CAP/xml_generados/upd.xml"
    respx.get(FEED).mock(return_value=httpx.Response(200, content=feed(URL_SINT, url_upd)))
    respx.get(URL_SINT).mock(return_value=httpx.Response(200, content=original))
    respx.get(url_upd).mock(return_value=httpx.Response(200, content=actualizacion))
    res = fuente().obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T13:00"))
    assert [a.identificador for a in res.alertas] == ["urn:oid:2.49.0.1.32.0.2026.10.04.09.00.00"]
