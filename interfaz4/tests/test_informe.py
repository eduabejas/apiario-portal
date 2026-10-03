import os
import re
from pathlib import Path

import pytest

from interfaz4.informe.constructor import (
    LEYENDA,
    construir_vista,
    dividir_mensaje,
    fmt_dif,
    fmt_num,
    generar,
    resumir,
    tabla_texto,
)
from interfaz4.informe.recoleccion import DatosInforme, recolectar
from interfaz4.modelos import PuntoHorario
from tests.conftest import FIXTURES, local
from tests.datos_prueba import AHORA_12H, recolector_offline, visita_domingo

SNAPSHOTS = FIXTURES / "snapshots"
LISTA_NEGRA = ("recomend", "ideal", "riesgo", "conviene", "evitar", "favorable", "desfavorable")


@pytest.fixture
def datos_12h(config, tmp_path) -> DatosInforme:
    return recolectar(config, visita_domingo(), 12, AHORA_12H, recolector_offline(tmp_path))


def _sin_alertas(config, tmp_path, **kw) -> DatosInforme:
    return recolectar(config, visita_domingo(), 12, AHORA_12H, recolector_offline(tmp_path, alertas=[], **kw))


# --------------------------------------------------------------- formatos


def test_fmt_num_coma_decimal_y_sd():
    assert fmt_num(14.25, 1) in ("14,2", "14,3")
    assert fmt_num(3.0, 1) == "3,0"
    assert fmt_num(84.4, 0) == "84"
    assert fmt_num(-0.04, 1) == "0,0"
    assert fmt_num(-2.5, 1) == "-2,5"
    assert fmt_num(None, 1) == "s/d"


def test_fmt_dif():
    assert fmt_dif(0.4, 2.1, 1) == "+1,7"
    assert fmt_dif(19.8, 19.1, 1) == "−0,7"
    assert fmt_dif(5.0, 5.0, 1) == "±0,0"
    assert fmt_dif(0.44, 2.06, 1) == "+1,7"  # se resta lo que se muestra (0,4 → 2,1)


def test_tabla_texto_alineada():
    t = tabla_texto(["", "A", "B"], [["fila", "1", "22"], ["otra fila", "333", "4"]]).splitlines()
    assert t[1] == "fila         1  22"
    assert t[2] == "otra fila  333   4"


# --------------------------------------------------------------- resumen


def _p(h, **kw):
    return PuntoHorario(hora_local=local(f"2026-10-10T{h:02d}:00"), **kw)


def test_resumir_min_max_suma_y_rumbo():
    r = resumir(
        [
            _p(9, temp_c=14.2, hr_pct=84, viento_kmh=12, viento_dir_cardinal="SE", precip_mm=0.0),
            _p(10, temp_c=16.0, hr_pct=76, viento_kmh=18, viento_dir_cardinal="SE", precip_mm=0.2),
            _p(11, temp_c=19.8, hr_pct=61, viento_kmh=18, viento_dir_cardinal="ESE", precip_mm=0.3),
        ]
    )
    assert (r.temp_min, r.temp_max, r.hr_min, r.hr_max) == (14.2, 19.8, 61, 84)
    assert (r.viento_max, r.viento_rumbo) == (18, "SE")  # primera hora con el máximo
    assert r.precip_total == pytest.approx(0.5) and r.precip_completa
    assert r.rafaga_max is None and r.prob_max is None


def test_resumir_lluvia_parcial_no_se_rellena():
    r = resumir([_p(9, precip_mm=0.4), _p(10), _p(11, precip_mm=0.1), _p(12, precip_mm=0.0)])
    assert r.precip_total == pytest.approx(0.5)
    assert (r.precip_horas, r.horas) == (3, 4) and not r.precip_completa


def test_resumir_sin_datos():
    r = resumir([_p(9), _p(10)])
    assert r.temp_min is None and r.viento_max is None and r.precip_total is None


# ----------------------------------------------------------- informe completo


def test_asunto_y_encabezado(datos_12h):
    r = generar(datos_12h)
    assert r.asunto == "🐝 Visita Apiario de producción melífera 04/10 09:00–13:00 · informe 12 h"
    lineas = r.texto.splitlines()
    assert lineas[0] == "🐝 Informe de visita — 12 h antes"
    assert lineas[1] == "Apiario de producción melífera · Berisso, Buenos Aires (-34.8892, -57.8279)"
    assert lineas[2] == "Visita: domingo 04/10/2026 · 09:00–13:00 (hora Argentina)"
    assert lineas[3] == "Responsable: Eduardo Mendoza · Notas: Revisión de núcleos"
    assert lineas[4] == "Generado: sábado 03/10/2026 21:17 · Último informe programado para esta visita"


def test_secciones_en_orden(datos_12h):
    texto = generar(datos_12h).texto
    orden = [
        "ALERTAS SMN",
        "RESUMEN DE LA VENTANA",
        "ANTES DE LA VISITA (21:00 del sábado → 09:00 del domingo)",
        "DETALLE HORARIO — SMN WRF (ciclo 03/10 12 UTC)",
        "DETALLE HORARIO — MET Norway (actualizado 03/10 19:21 UTC)",
        "FUENTES Y LICENCIAS",
        LEYENDA,
    ]
    posiciones = [texto.index(s) for s in orden]
    assert posiciones == sorted(posiciones)


def test_proximo_informe_en_el_de_24h(config, tmp_path):
    from datetime import UTC, datetime

    ahora = datetime(2026, 10, 3, 12, 17, tzinfo=UTC)  # 09:17 del sábado
    datos = recolectar(config, visita_domingo(), 24, ahora, recolector_offline(tmp_path, ahora=ahora, alertas=[]))
    assert datos.proximo_informe == local("2026-10-03T21:00")
    texto = generar(datos).texto
    assert "Próximo informe: ~21:00 del sábado" in texto
    assert "informe 24 h" in generar(datos).asunto


def test_tramo_previo_suma_por_fuente(datos_12h):
    assert datos_12h.tramo_desde == local("2026-10-03T21:00")
    assert datos_12h.tramo_hasta == local("2026-10-04T09:00")
    assert all(len(s.puntos) == 12 for s in datos_12h.series_previas)
    vista = construir_vista(datos_12h)
    assert vista.tramo_partes == ["SMN WRF 0,0 mm", "MET Norway 0,0 mm"]


def test_sin_tramo_si_el_envio_es_en_la_hora_de_inicio(config, tmp_path):
    from datetime import UTC, datetime

    ahora = datetime(2026, 10, 4, 12, 10, tzinfo=UTC)  # 09:10, visita 09:30
    visita = visita_domingo(desde="09:30")
    datos = recolectar(config, visita, 12, ahora, recolector_offline(tmp_path, ahora=ahora, alertas=[]))
    assert datos.tramo_desde is None and datos.series_previas == []
    assert "ANTES DE LA VISITA" not in generar(datos).texto


def test_atribuciones_y_emision_siempre_presentes(datos_12h):
    r = generar(datos_12h)
    for formato in (r.html, r.texto, "\n".join(r.chat)):
        assert "Pronóstico WRF-SMN © Servicio Meteorológico Nacional (Argentina), CC BY 2.5 AR." in formato
        assert "Datos de MET Norway (api.met.no), CC BY 4.0." in formato
        assert "Alertas: Servicio Meteorológico Nacional (CAP), CC BY 4.0." in formato
        assert "Este informe presenta datos de pronóstico sin interpretación." in formato
        assert "ciclo 03/10 12 UTC" in formato
        assert "actualizado 03/10 19:21 UTC" in formato


def test_alerta_se_copia_textual(datos_12h):
    r = generar(datos_12h)
    instruccion = "Evitá salir. Para minimizar el riesgo de ser alcanzado por un rayo, no permanezcas en espacios abiertos."
    assert instruccion in r.texto and instruccion in r.html
    assert "ALERTA AMARILLA POR TORMENTAS" in r.texto
    assert "Vigencia: desde domingo 04/10/2026 10:00 hasta domingo 04/10/2026 18:00" in r.texto


@pytest.mark.parametrize(
    "kw,mensaje",
    [
        ({}, "Sin alertas SMN vigentes para este punto y horario."),
        ({"alertas_disponibles": False}, "Alertas SMN no disponibles en esta ejecución."),
    ],
)
def test_estados_de_alertas(config, tmp_path, kw, mensaje):
    r = generar(_sin_alertas(config, tmp_path, **kw))
    assert mensaje in r.texto and mensaje in r.html


def test_alertas_deshabilitadas(config, tmp_path):
    rec = recolector_offline(tmp_path, alertas=[])
    rec.fuente_alertas = None
    r = generar(recolectar(config, visita_domingo(), 12, AHORA_12H, rec))
    assert "Alertas SMN: fuente deshabilitada en la configuración." in r.texto
    assert "Alertas: Servicio Meteorológico Nacional (CAP)" not in r.texto


@pytest.mark.parametrize("estado", ["sin", "no_disponible", "deshabilitada"])
def test_lista_negra_de_palabras_valorativas(config, tmp_path, estado):
    """El informe (sin el texto textual de alertas del SMN) no interpreta."""
    rec = recolector_offline(tmp_path, alertas=[], alertas_disponibles=(estado != "no_disponible"))
    if estado == "deshabilitada":
        rec.fuente_alertas = None
    datos = recolectar(config, visita_domingo(notas=None), 12, AHORA_12H, rec)
    previo = datos.model_copy(update={"hito": 24})
    r = generar(datos, previo)
    todo = "\n".join([r.asunto, r.html, r.texto, *r.chat]).lower()
    for palabra in LISTA_NEGRA:
        assert palabra not in todo, palabra


def test_lista_negra_en_plantillas_y_constructor():
    """Ninguna plantilla ni texto fijo del constructor contiene palabras valorativas."""
    base = Path(__file__).resolve().parent.parent / "src" / "interfaz4" / "informe"
    archivos = [*base.glob("plantillas/*.j2"), base / "constructor.py"]
    for archivo in archivos:
        contenido = archivo.read_text(encoding="utf-8").lower()
        for palabra in LISTA_NEGRA:
            assert palabra not in contenido, f"{palabra} en {archivo.name}"


def test_sd_y_nota_de_huecos(datos_12h):
    vista = construir_vista(datos_12h)
    resumen = dict(vista.resumen)
    assert resumen["Ráfaga máx (km/h)"] == ["s/d", "s/d"]
    assert resumen["Prob. precipitación máx (%)"] == ["s/d", "s/d"]
    assert any("no publican esos datos" in n for n in vista.notas_resumen)


def test_comparacion_24_12(datos_12h):
    previo = datos_12h.model_copy(deep=True)
    previo.hito = 24
    previo.generado = local("2026-10-03T09:17")
    for p in previo.series[0].puntos:
        p.precip_mm = 0.1
        p.temp_c = (p.temp_c or 0) + 1.0
    vista = construir_vista(datos_12h, previo)
    assert vista.cambios_titulo == "CAMBIOS RESPECTO AL INFORME DE 24 H (generado sábado 03/10/2026 09:17)"
    assert "Precip. total SMN WRF: 0,4 → 0,0 mm (−0,4)" in vista.cambios
    assert any(c.startswith("Temp. mín SMN WRF: 12,7 → 11,7 °C (−1,0)") for c in vista.cambios)
    assert "Precip. total MET Norway: 0,0 → 0,0 mm (±0,0)" in vista.cambios
    texto = generar(datos_12h, previo).texto
    assert "CAMBIOS RESPECTO AL INFORME DE 24 H" in texto


def test_sin_comparacion_si_no_hay_previo_o_esta_apagada(datos_12h):
    assert "CAMBIOS RESPECTO" not in generar(datos_12h).texto
    previo = datos_12h.model_copy(update={"hito": 24})
    assert "CAMBIOS RESPECTO" not in generar(datos_12h, previo, comparar_24_12=False).texto


def test_html_escapa_texto_de_usuario(config, tmp_path):
    datos = recolectar(
        config, visita_domingo(notas="<script>alert(1)</script>"), 12, AHORA_12H, recolector_offline(tmp_path, alertas=[])
    )
    r = generar(datos)
    assert "<script>" not in r.html and "&lt;script&gt;" in r.html


def test_snapshot_json_reproduce_el_mismo_informe(datos_12h):
    copia = DatosInforme.model_validate_json(datos_12h.model_dump_json())
    assert generar(copia).texto == generar(datos_12h).texto


def test_dividir_mensaje_respeta_limite_y_bloques():
    secciones = [f"*Sección {i}*\n```\n" + "\n".join(f"fila {i}-{j} " + "x" * 40 for j in range(20)) + "\n```\n" for i in range(6)]
    texto = "\n".join(secciones)
    partes = dividir_mensaje(texto, limite=1500)
    assert len(partes) > 1 and all(len(p) <= 1500 for p in partes)
    assert all(p.count("```") % 2 == 0 for p in partes)
    assert dividir_mensaje("corto") == ["corto"]


# ------------------------------------------------------------- snapshots


@pytest.mark.parametrize("formato", ["texto", "chat", "html"])
def test_snapshot_de_plantillas(datos_12h, formato):
    r = generar(datos_12h)
    contenido = {"texto": r.texto, "chat": "\n\n=====\n\n".join(r.chat), "html": r.html}[formato]
    archivo = SNAPSHOTS / f"informe_12h.{ {'texto': 'txt', 'chat': 'chat.txt', 'html': 'html'}[formato] }"
    if os.environ.get("ACTUALIZAR_SNAPSHOTS") == "1" or not archivo.exists():
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_text(contenido, encoding="utf-8")
    assert contenido == archivo.read_text(encoding="utf-8")


def test_html_sin_recursos_externos(datos_12h):
    html = generar(datos_12h).html
    assert not re.search(r"<img|<link|<script|url\(", html, re.IGNORECASE)
