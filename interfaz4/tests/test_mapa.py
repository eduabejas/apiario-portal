"""Tests del mapa de lluvia (Parte B v1.1): render offline, entrega por CID
en el correo, y aislamiento de fallas (nunca bloquea el envío)."""

from __future__ import annotations

import email
import email.policy
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from interfaz4.informe.constructor import InformeRenderizado, VistaInforme, VistaMapa, generar
from interfaz4.informe.mapa import cargar_costa, render_mapa
from interfaz4.informe.recoleccion import DatosInforme
from interfaz4.notificar.correo_smtp import armar_mensaje
from interfaz4.modelos import Apiario, Visita

FIXTURES = Path(__file__).resolve().parent / "fixtures"
RAIZ = Path(__file__).resolve().parent.parent


def _costa_real():
    costa_path = RAIZ / "assets" / "costa_rdp.geojson"
    return cargar_costa(costa_path) if costa_path.exists() else []


def test_render_mapa_devuelve_png_bajo_80kb():
    lat = np.linspace(-35.9, -33.9, 50)[:, None].repeat(50, 1)
    lon = np.linspace(-58.8, -56.8, 50)[None, :].repeat(50, 0)
    pp = np.zeros((50, 50), dtype="f4")
    pp[20:30, 20:30] = 3.0  # mancha de lluvia
    png = render_mapa(lat, lon, pp, -34.89, -57.83, _costa_real(), "Mapa prueba")
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(png) <= 80 * 1024, f"PNG grande: {len(png)} bytes"


def test_render_mapa_sin_lluvia_tambien_funciona():
    lat = np.linspace(-35.9, -33.9, 20)[:, None].repeat(20, 1)
    lon = np.linspace(-58.8, -56.8, 20)[None, :].repeat(20, 0)
    pp = np.zeros((20, 20), dtype="f4")
    png = render_mapa(lat, lon, pp, -34.89, -57.83, [], "sin lluvia")
    assert png.startswith(b"\x89PNG")


def test_mensaje_con_mapa_adjunta_imagen_por_cid():
    """El correo tiene multipart/alternative → multipart/related → image/png,
    y el Content-ID del PNG coincide con el `src` del `<img>` del HTML."""
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # PNG de juguete, igual sirve
    cid = "mapa.1@interfaz4"
    html = f'<p><img src="cid:{cid}"></p>'
    msg = armar_mensaje("asunto", html, "texto", "a@b.com", ["c@d.com"], imagenes=[(cid, png)])
    partes = list(msg.walk())
    tipos = [p.get_content_type() for p in partes]
    assert "multipart/alternative" in tipos
    assert "multipart/related" in tipos
    assert "image/png" in tipos
    img = next(p for p in partes if p.get_content_type() == "image/png")
    assert img.get("Content-ID") == f"<{cid}>"
    html_part = next(p for p in partes if p.get_content_type() == "text/html")
    assert f"cid:{cid}" in html_part.get_content()


def test_mensaje_sin_imagenes_no_tiene_related():
    msg = armar_mensaje("asunto", "<p>x</p>", "x", "a@b.com", ["c@d.com"])
    tipos = {p.get_content_type() for p in msg.walk()}
    assert "multipart/related" not in tipos
    assert "image/png" not in tipos


def test_mapa_que_falla_no_rompe_el_informe(monkeypatch):
    """Si render_mapa lanza, el informe sale igual sin mapa."""
    from interfaz4.informe import constructor as c

    def _explotar(*a, **kw):
        raise RuntimeError("falló matplotlib")

    monkeypatch.setattr("interfaz4.informe.mapa.render_mapa", _explotar)
    datos = DatosInforme(
        visita=Visita(
            id="v1", apiario="t", fecha="2026-10-12",  # type: ignore[arg-type]
            desde="09:00", hasta="13:00", responsable="x",  # type: ignore[arg-type]
        ),
        apiario=Apiario(id="t", nombre="t", lat=-34.89, lon=-57.83),
        hito=24,
        generado=datetime(2026, 10, 12, 11, 0, tzinfo=UTC),
        series=[],
        fuentes_deshabilitadas=["smn_wrf", "metno", "open_meteo", "ecmwf_ens"],
        mapa_pp_caja={
            "lat2d": np.zeros((5, 5)),
            "lon2d": np.zeros((5, 5)),
            "pp": np.zeros((5, 5), "f4"),
            "iy_centro": 2,
            "ix_centro": 2,
            "init_utc": datetime(2026, 10, 12, 12, tzinfo=UTC),
            "horas": 4,
        },
    )
    render = c.generar(datos, comparar_24_12=False)
    assert isinstance(render, InformeRenderizado)
    assert render.imagenes_inline == []  # el mapa quedó fuera
    assert "MAPA DE LLUVIA" not in render.texto


def test_renderizado_expone_el_png_para_adjuntar():
    vista = VistaInforme(
        asunto="x", titulo="t", apiario_linea="", visita_linea="", responsable_linea="",
        generado_linea="", alertas_estado="deshabilitada", alertas_mensaje="",
        alertas=[], columnas=[], resumen=[], notas_resumen=[],
        tramo_titulo=None, tramo_partes=[], detalles=[],
        cambios_titulo=None, cambios=[],
        pie_fuentes=[], atribuciones=[],
        mapa=VistaMapa(cid="x@y", titulo="t", texto_alt="alt", png=b"\x89PNG\r\n\x1a\nxx"),
    )
    from interfaz4.informe.constructor import renderizar

    render = renderizar(vista)
    assert render.imagenes_inline == [("x@y", b"\x89PNG\r\n\x1a\nxx")]
    assert 'src="cid:x@y"' in render.html
