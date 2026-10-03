import math

import pytest

from interfaz4 import normalizar
from interfaz4.normalizar import Convencion, armar_puntos
from tests.conftest import local


def test_ms_a_kmh():
    assert normalizar.ms_a_kmh(10) == pytest.approx(36.0)
    assert normalizar.ms_a_kmh(0) == 0
    assert normalizar.ms_a_kmh(None) is None
    assert normalizar.ms_a_kmh(float("nan")) is None


@pytest.mark.parametrize(
    "grados,rumbo",
    [
        (0, "N"), (11.24, "N"), (11.25, "NNE"), (22.5, "NNE"), (45, "NE"), (67.5, "ENE"),
        (90, "E"), (112.5, "ESE"), (135, "SE"), (157.5, "SSE"), (180, "S"), (202.5, "SSO"),
        (225, "SO"), (247.5, "OSO"), (270, "O"), (292.5, "ONO"), (315, "NO"), (337.5, "NNO"),
        (348.74, "NNO"), (348.75, "N"), (359.9, "N"), (360, "N"), (-90, "O"), (450, "E"),
    ],
)
def test_grados_a_cardinal_16_rumbos(grados, rumbo):
    assert normalizar.grados_a_cardinal(grados) == rumbo


def test_cardinal_sin_dato():
    assert normalizar.grados_a_cardinal(None) is None
    assert normalizar.grados_a_cardinal(math.inf) is None


@pytest.mark.parametrize("v", [None, float("nan"), float("inf"), 1e20, -1e20, "abc", True])
def test_valor_descarta_rellenos(v):
    assert normalizar.valor(v) is None


def test_valor_acepta_numeros():
    assert normalizar.valor("2.5") == 2.5
    assert normalizar.valor(0) == 0.0


def _datos():
    # instantáneos en 09, 10, 11 y 12; acumulado "etiquetado" con su hora para ver qué fila lo toma
    inst = {local(f"2026-10-10T{h:02d}:00"): {"temp_c": float(h)} for h in range(9, 14)}
    acu = {local(f"2026-10-10T{h:02d}:00"): {"precip_mm": float(h)} for h in range(9, 14)}
    filas = [local(f"2026-10-10T{h:02d}:00") for h in (9, 10, 11, 12)]
    return filas, inst, acu


def test_convencion_hora_que_termina_toma_h_mas_1():
    """SMN WRF y Open-Meteo: el valor en t es (t−1h, t] → la fila H usa t=H+1."""
    filas, inst, acu = _datos()
    puntos = armar_puntos(filas, inst, acu, Convencion.HORA_QUE_TERMINA)
    assert [p.temp_c for p in puntos] == [9, 10, 11, 12]
    assert [p.precip_mm for p in puntos] == [10, 11, 12, 13]


def test_convencion_hora_que_empieza_toma_h():
    """MET Norway: next_1_hours en t es [t, t+1h) → la fila H usa t=H."""
    filas, inst, acu = _datos()
    puntos = armar_puntos(filas, inst, acu, Convencion.HORA_QUE_EMPIEZA)
    assert [p.precip_mm for p in puntos] == [9, 10, 11, 12]


def test_claves_utc_y_local_son_equivalentes():
    from interfaz4 import tiempo

    filas = [local("2026-10-10T09:00")]
    inst = {tiempo.a_utc(local("2026-10-10T09:00")): {"temp_c": 15.0}}
    acu = {tiempo.a_utc(local("2026-10-10T10:00")): {"precip_mm": 0.4}}
    p = armar_puntos(filas, inst, acu, Convencion.HORA_QUE_TERMINA)[0]
    assert p.temp_c == 15.0 and p.precip_mm == 0.4
    assert p.hora_local.utcoffset().total_seconds() == -3 * 3600


def test_faltantes_quedan_en_none_sin_rellenar():
    filas = [local("2026-10-10T09:00"), local("2026-10-10T10:00")]
    inst = {local("2026-10-10T09:00"): {"temp_c": 14.0, "viento_kmh": 10.0, "viento_dir_grados": 135}}
    puntos = armar_puntos(filas, inst, {}, Convencion.HORA_QUE_EMPIEZA)
    assert puntos[0].viento_dir_cardinal == "SE"
    assert puntos[0].precip_mm is None and puntos[0].rafaga_kmh is None and puntos[0].prob_precip_pct is None
    segunda = puntos[1]
    assert all(
        getattr(segunda, c) is None
        for c in ("temp_c", "hr_pct", "viento_kmh", "viento_dir_grados", "viento_dir_cardinal", "precip_mm")
    )
