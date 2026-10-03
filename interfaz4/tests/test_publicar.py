import json

from interfaz4.publicar import exportar
from tests.conftest import local
from tests.test_motor import CorreoFalso, motor, nueva_visita


def test_exporta_estado_sin_correos_e_informes(config, tmp_path):
    v = nueva_visita(config, correo="privado@example.com", notas="Revisión de núcleos")
    motor(config, tmp_path, correo=CorreoFalso()).ejecutar(local("2026-10-03T09:17"))
    assert exportar(config, local("2026-10-03T09:20")) is True
    publico = config.rutas.publico_dir
    texto = (publico / "estado.json").read_text(encoding="utf-8")
    assert "privado@example.com" not in texto and "apicultor@example.com" not in texto
    doc = json.loads(texto)
    assert doc["version"] == 1 and doc["hitos_horas"] == [24, 12]
    assert doc["apiarios"]["produccion_miel"]["lat"] == -34.8892
    assert doc["fuentes"]["open_meteo"] == {"nombre": "Open-Meteo", "habilitada": False}
    [vis] = doc["visitas"]
    assert vis["id"] == v.id and vis["notas"] == "Revisión de núcleos"
    h24, h12 = vis["hitos"]
    assert h24 == {
        "horas": 24,
        "programado": "2026-10-03T09:00-03:00",
        "estado": "enviado",
        "momento": "2026-10-03T09:17-03:00",
        "canales": {"correo": "ok", "google_chat": "deshabilitado"},
        "errores": None,
        "detalle": None,
        "informe": f"informes/{v.id}_24.html",
    }
    assert h12["estado"] == "pendiente" and h12["informe"] is None
    html = (publico / h24["informe"]).read_text(encoding="utf-8")
    assert "Informe de visita — 24 h antes" in html
    # Sin cambios → no reescribe nada (no genera commits vacíos).
    assert exportar(config, local("2026-10-03T10:20")) is False


def test_errores_de_canal_visibles_y_poda_de_informes(config, tmp_path):
    v = nueva_visita(config)
    motor(config, tmp_path, correo=CorreoFalso(fallar=True)).ejecutar(local("2026-10-03T09:17"))
    exportar(config, local("2026-10-03T09:20"))
    doc = json.loads((config.rutas.publico_dir / "estado.json").read_text(encoding="utf-8"))
    h24 = doc["visitas"][0]["hitos"][0]
    assert h24["estado"] == "error" and h24["canales"]["correo"] == "error"
    assert h24["errores"]["correo"].startswith("correo sin configurar")
    huerfano = config.rutas.publico_dir / "informes" / "viejo_24.html"
    huerfano.write_text("x", encoding="utf-8")
    assert exportar(config, local("2026-10-03T09:30")) is True
    assert not huerfano.exists()
    assert (config.rutas.publico_dir / "informes" / f"{v.id}_24.html").exists()


def test_visitas_viejas_salen_de_la_web(config, tmp_path):
    nueva_visita(config)
    exportar(config, local("2026-10-03T09:00"))
    assert len(json.loads((config.rutas.publico_dir / "estado.json").read_text())["visitas"]) == 1
    exportar(config, local("2026-12-31T09:00"))
    assert json.loads((config.rutas.publico_dir / "estado.json").read_text())["visitas"] == []
