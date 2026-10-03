from datetime import UTC, date, datetime, time

import pytest

from interfaz4 import tiempo
from tests.conftest import local


def test_zona_argentina_es_utc_menos_3():
    dt = tiempo.localizar(date(2026, 10, 10), time(9, 0))
    assert dt.utcoffset().total_seconds() == -3 * 3600
    assert tiempo.a_utc(dt) == datetime(2026, 10, 10, 12, 0, tzinfo=UTC)


def test_conversion_utc_a_local_cruza_el_dia():
    utc = datetime(2026, 10, 10, 1, 30, tzinfo=UTC)
    loc = tiempo.a_local(utc)
    assert (loc.day, loc.hour, loc.minute) == (9, 22, 30)


def test_naive_se_rechaza():
    with pytest.raises(ValueError):
        tiempo.a_utc(datetime(2026, 10, 10, 9, 0))


def test_filas_ventana_horas_en_punto():
    filas = tiempo.filas_ventana(local("2026-10-10T09:00"), local("2026-10-10T13:00"))
    assert [f.hour for f in filas] == [9, 10, 11, 12]


def test_filas_ventana_con_minutos():
    filas = tiempo.filas_ventana(local("2026-10-10T09:30"), local("2026-10-10T11:15"))
    assert [f.hour for f in filas] == [9, 10, 11]


def test_filas_ventana_menos_de_una_hora():
    filas = tiempo.filas_ventana(local("2026-10-10T09:10"), local("2026-10-10T09:50"))
    assert [f.hour for f in filas] == [9]


def test_filas_ventana_invalida():
    with pytest.raises(ValueError):
        tiempo.filas_ventana(local("2026-10-10T11:00"), local("2026-10-10T09:00"))


def test_piso_y_techo():
    dt = local("2026-10-10T09:17")
    assert tiempo.piso_hora(dt) == local("2026-10-10T09:00")
    assert tiempo.techo_hora(dt) == local("2026-10-10T10:00")
    assert tiempo.techo_hora(local("2026-10-10T09:00")) == local("2026-10-10T09:00")


def test_sumar_horas_cruza_medianoche():
    assert tiempo.sumar_horas(local("2026-10-09T21:00"), 12) == local("2026-10-10T09:00")
    assert tiempo.sumar_horas(local("2026-10-10T09:00"), -24) == local("2026-10-09T09:00")


def test_parsear_momento():
    assert tiempo.parsear_momento("2026-10-09T09:17-03:00") == local("2026-10-09T09:17")
    assert tiempo.parsear_momento("2026-10-09T12:17Z") == local("2026-10-09T09:17")
    assert tiempo.parsear_momento("2026-10-09T09:17").tzinfo is not None


@pytest.mark.parametrize(
    "valor,esperado",
    [("09:00", time(9, 0)), ("13:45", time(13, 45)), (780, time(13, 0)), (time(8, 5), time(8, 5))],
)
def test_parsear_hora(valor, esperado):
    assert tiempo.parsear_hora(valor) == esperado


@pytest.mark.parametrize("valor", ["9", "25:00", "09:60", "9:5", "", True, -1, 1440])
def test_parsear_hora_invalida(valor):
    with pytest.raises(ValueError):
        tiempo.parsear_hora(valor)


def test_formatos_en_espanol():
    dt = local("2026-10-10T09:05")
    assert tiempo.fmt_dia_fecha(dt) == "sábado 10/10/2026"
    assert tiempo.fmt_dd_mm(dt) == "10/10"
    assert tiempo.fmt_hora(dt) == "09:05"
    assert tiempo.fmt_momento(dt) == "sábado 10/10/2026 09:05"
    assert tiempo.fmt_hora_dia(local("2026-10-09T21:00")) == "21:00 del viernes"
    assert tiempo.fmt_utc_ciclo(datetime(2026, 10, 9, 6, tzinfo=UTC)) == "09/10 06 UTC"
