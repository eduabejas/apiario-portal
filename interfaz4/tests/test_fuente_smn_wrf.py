"""Fuente SMN WRF contra un recorte real del ciclo 2026-10-03 12 UTC
(tests/fixtures/smn_wrf, generado con scripts/generar_fixture_wrf.py)."""

from datetime import UTC, datetime

import fsspec
import h5py
import pytest

from interfaz4.fuentes.smn_wrf import (
    CacheGrilla,
    FuenteSMNWRF,
    RepositorioWRF,
    ciclos_candidatos,
    decodificar_tiempo,
    indice_mas_cercano,
)
from interfaz4.modelos import Apiario
from tests.conftest import FIXTURES, local

RAIZ = FIXTURES / "smn_wrf"
DIR_CICLO = RAIZ / "DATA/WRF/DET/2026/10/03/12"
INIT = datetime(2026, 10, 3, 12, tzinfo=UTC)
APIARIO = Apiario(id="produccion_miel", nombre="P", lat=-34.889180362505506, lon=-57.82789829443907)
# 21:17 del sábado 03/10 en Argentina (el ciclo de las 18 UTC no está en el fixture)
AHORA = datetime(2026, 10, 4, 0, 17, tzinfo=UTC)


def directo(plazo: int, variable: str) -> float:
    """Oráculo independiente: lee el centro del recorte (4, 4) con h5py."""
    with h5py.File(DIR_CICLO / f"WRFDETAR_01H_20261003_12_{plazo:03d}.nc", "r") as h:
        return float(h[variable][0, 4, 4])


class RepoEspia(RepositorioWRF):
    def __init__(self, **kw):
        super().__init__(fs=fsspec.filesystem("file"), raiz=str(RAIZ), **kw)
        self.lecturas: list[tuple[str, list[str]]] = []
        self.latlon = 0
        self.fallar_en: set[str] = set()

    def leer(self, ruta, iy, ix, variables):
        if any(ruta.endswith(f) for f in self.fallar_en):
            raise OSError("lectura interrumpida")
        self.lecturas.append((ruta.rsplit("/", 1)[-1], list(variables)))
        return super().leer(ruta, iy, ix, variables)

    def leer_latlon(self, ruta):
        self.latlon += 1
        return super().leer_latlon(ruta)


def fuente(tmp_path, repo=None, ahora=AHORA):
    return FuenteSMNWRF(repo or RepoEspia(), CacheGrilla(tmp_path / "cache_grilla.json"), reloj=lambda: ahora)


def test_ciclos_candidatos_de_mas_reciente_a_mas_antiguo():
    assert ciclos_candidatos(AHORA) == [
        datetime(2026, 10, 4, 0, tzinfo=UTC),
        datetime(2026, 10, 3, 18, tzinfo=UTC),
        datetime(2026, 10, 3, 12, tzinfo=UTC),
        datetime(2026, 10, 3, 6, tzinfo=UTC),
        datetime(2026, 10, 3, 0, tzinfo=UTC),
    ]


def test_alineacion_de_intervalos_con_datos_reales(tmp_path):
    serie = fuente(tmp_path).obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T13:00"))
    assert not serie.errores
    assert serie.emitido_utc == INIT and serie.detalle_emision == "ciclo 03/10 12 UTC"
    assert [p.hora_local.hour for p in serie.puntos] == [9, 10, 11, 12]
    for i, p in enumerate(serie.puntos):
        plazo_h = 24 + i  # 09:00 local = 12 UTC = init + 24 h
        assert p.temp_c == pytest.approx(directo(plazo_h, "T2"), abs=0.01)
        assert p.hr_pct == pytest.approx(directo(plazo_h, "HR2"), abs=0.05)
        assert p.viento_kmh == pytest.approx(directo(plazo_h, "magViento10") * 3.6, abs=0.01)
        assert p.viento_dir_grados == pytest.approx(directo(plazo_h, "dirViento10"), abs=0.05)
        # PP del archivo válido en t es (t−1h, t] → la fila H usa el archivo de H+1
        assert p.precip_mm == pytest.approx(directo(plazo_h + 1, "PP"), abs=0.001)
        assert p.rafaga_kmh is None and p.prob_precip_pct is None


def test_indice_de_grilla_se_cachea(tmp_path):
    repo = RepoEspia()
    fuente(tmp_path, repo).obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T10:00"))
    assert repo.latlon == 1
    import json

    cache = json.loads((tmp_path / "cache_grilla.json").read_text())
    assert cache["forma"] == [9, 9]
    punto = cache["puntos"]["-34.889180,-57.827898"]
    assert (punto["iy"], punto["ix"]) == (4, 4)
    assert punto["dist_km"] == pytest.approx(1.72, abs=0.01)
    # Otra ejecución: usa el caché, no vuelve a leer lat/lon.
    repo2 = RepoEspia()
    fuente(tmp_path, repo2).obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T10:00"))
    assert repo2.latlon == 0


def test_cache_con_otra_forma_se_recalcula(tmp_path):
    CacheGrilla(tmp_path / "cache_grilla.json").guardar(APIARIO.lat, APIARIO.lon, (1249, 999), {"iy": 621, "ix": 662})
    repo = RepoEspia()
    serie = fuente(tmp_path, repo).obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T10:00"))
    assert repo.latlon == 1 and serie.puntos[0].temp_c is not None


def test_solo_precipitacion_lee_solo_pp(tmp_path):
    repo = RepoEspia()
    serie = fuente(tmp_path, repo).obtener(
        APIARIO, local("2026-10-03T21:00"), local("2026-10-04T09:00"), variables="precipitacion"
    )
    assert len(serie.puntos) == 12
    lecturas_datos = [v for _, v in repo.lecturas if v]
    assert lecturas_datos and all(v == ["PP"] for v in lecturas_datos)
    assert [n for n, v in repo.lecturas if v][0].endswith("_013.nc")  # fila 21:00 local → archivo de 01 UTC
    assert serie.puntos[0].temp_c is None
    assert serie.puntos[0].precip_mm == pytest.approx(directo(13, "PP"), abs=0.001)


def test_eleccion_de_ciclo_salta_ciclos_incompletos():
    class Stub(RepositorioWRF):
        def plazos_disponibles(self, init):
            return {
                datetime(2026, 10, 4, 0, tzinfo=UTC): set(),
                datetime(2026, 10, 3, 18, tzinfo=UTC): set(range(11)),  # subiendo
                datetime(2026, 10, 3, 12, tzinfo=UTC): set(range(73)),
            }.get(init, set(range(73)))

    f = FuenteSMNWRF(Stub(fs=object()), reloj=lambda: AHORA)
    init, _ = f.elegir_ciclo(AHORA, datetime(2026, 10, 4, 16, tzinfo=UTC))
    assert init == datetime(2026, 10, 3, 12, tzinfo=UTC)
    # Si ningún ciclo cubre el fin (más allá de +72 h), se usa el más reciente con archivos.
    init, _ = f.elegir_ciclo(AHORA, datetime(2026, 10, 8, 0, tzinfo=UTC))
    assert init == datetime(2026, 10, 3, 18, tzinfo=UTC)


def test_horas_fuera_del_ciclo_quedan_sd(tmp_path):
    # El fixture llega hasta el plazo 030 (18 UTC del 04/10 = 15:00 local).
    serie = fuente(tmp_path).obtener(APIARIO, local("2026-10-04T14:00"), local("2026-10-04T17:00"))
    assert serie.puntos[0].temp_c is not None  # 14:00 local = plazo 029
    assert serie.puntos[0].precip_mm is not None  # usa plazo 030
    assert serie.puntos[1].precip_mm is None and serie.puntos[2].temp_c is None
    assert any("fuera de lo publicado" in e for e in serie.errores)


def test_falla_de_un_archivo_degrada_solo_esa_hora(tmp_path):
    repo = RepoEspia()
    repo.fallar_en = {"_025.nc"}
    serie = fuente(tmp_path, repo).obtener(APIARIO, local("2026-10-04T09:00"), local("2026-10-04T11:00"))
    assert serie.puntos[0].temp_c is not None
    assert serie.puntos[0].precip_mm is None  # PP de la fila 09 sale del plazo 025
    assert serie.puntos[1].temp_c is None  # instantáneos de la fila 10 salen del plazo 025
    assert serie.puntos[1].precip_mm is not None
    assert any("plazo 025" in e for e in serie.errores)


def test_sin_ciclos_publicados(tmp_path):
    serie = fuente(tmp_path, ahora=datetime(2026, 11, 1, 12, tzinfo=UTC)).obtener(
        APIARIO, local("2026-11-02T09:00"), local("2026-11-02T10:00")
    )
    assert serie.puntos[0].temp_c is None
    assert "no hay ciclos" in serie.errores[0]


def test_decodificar_tiempo():
    assert decodificar_tiempo("hours since 2026-10-03T12:00:00", 12) == datetime(2026, 10, 4, 0, tzinfo=UTC)
    assert decodificar_tiempo("hours since 2026-10-03 12:00:00", 1.5) == datetime(2026, 10, 3, 13, 30, tzinfo=UTC)
    assert decodificar_tiempo("days since 2026-10-04 00:00:00", 0) == datetime(2026, 10, 4, tzinfo=UTC)
    with pytest.raises(ValueError):
        decodificar_tiempo("fortnights since 2026-01-01", 1)


def test_tiempo_del_fixture_conserva_la_convencion_original():
    with h5py.File(DIR_CICLO / "WRFDETAR_01H_20261003_12_012.nc", "r") as h:
        unidades = h["time"].attrs["units"]
        unidades = unidades.decode() if isinstance(unidades, bytes) else str(unidades)
        assert unidades.startswith("hours since 2026-10-03")
        assert float(h["time"][0]) == 12.0


def test_indice_mas_cercano_en_el_recorte():
    with h5py.File(DIR_CICLO / "WRFDETAR_01H_20261003_12_000.nc", "r") as h:
        iy, ix, d = indice_mas_cercano(h["lat"][...], h["lon"][...], APIARIO.lat, APIARIO.lon)
    assert (iy, ix) == (4, 4) and d == pytest.approx(1.72, abs=0.01)
