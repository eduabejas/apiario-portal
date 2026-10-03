import httpx
import pytest

from interfaz4.config import AjustesReintentos
from interfaz4.fuentes.base import ErrorFuente
from interfaz4.fuentes.http import ClienteHTTP, parece_challenge


def cliente(manejador, intentos=3):
    esperas = []
    c = ClienteHTTP(
        AjustesReintentos(http_intentos=intentos, http_backoff_seg=[2, 5, 15], timeout_seg=5),
        user_agent="interfaz4-test/0.1 contacto@example.com",
        transport=httpx.MockTransport(manejador),
        dormir=esperas.append,
    )
    return c, esperas


def test_reintenta_5xx_con_backoff():
    llamadas = []

    def manejador(req):
        llamadas.append(req)
        return httpx.Response(502) if len(llamadas) < 3 else httpx.Response(200, json={"ok": True})

    c, esperas = cliente(manejador)
    assert c.get("https://x.test/a").json() == {"ok": True}
    assert len(llamadas) == 3
    assert esperas == [2, 5]
    assert llamadas[0].headers["User-Agent"] == "interfaz4-test/0.1 contacto@example.com"


def test_agota_reintentos():
    c, esperas = cliente(lambda req: httpx.Response(500))
    with pytest.raises(ErrorFuente, match="3 intentos"):
        c.get("https://x.test/a")
    assert esperas == [2, 5]


def test_errores_de_red_se_reintentan():
    llamadas = []

    def manejador(req):
        llamadas.append(req)
        if len(llamadas) == 1:
            raise httpx.ConnectError("sin red")
        return httpx.Response(200, text="ok")

    c, _ = cliente(manejador)
    assert c.get("https://x.test/a").text == "ok"


def test_4xx_no_se_reintenta():
    llamadas = []

    def manejador(req):
        llamadas.append(req)
        return httpx.Response(429)

    c, esperas = cliente(manejador)
    assert c.get("https://x.test/a").status_code == 429
    assert len(llamadas) == 1 and esperas == []


def test_challenge_no_se_reintenta_ni_se_evade():
    llamadas = []
    html = "<html><title>Just a moment...</title><script src='/cdn-cgi/challenge-platform/x'></script></html>"

    def manejador(req):
        llamadas.append(req)
        return httpx.Response(503, text=html, headers={"content-type": "text/html"})

    c, _ = cliente(manejador)
    resp = c.get("https://x.test/a")
    assert parece_challenge(resp)
    assert len(llamadas) == 1


def test_parece_challenge():
    assert parece_challenge(httpx.Response(403))
    assert not parece_challenge(httpx.Response(200, text="<rss/>", headers={"content-type": "application/rss+xml"}))
    assert not parece_challenge(httpx.Response(503, text="mantenimiento", headers={"content-type": "text/plain"}))
