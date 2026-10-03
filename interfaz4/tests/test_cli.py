from datetime import UTC, datetime

import time_machine
from typer.testing import CliRunner

from interfaz4 import cli
from interfaz4.config import cargar_config
from tests.datos_prueba import recolector_offline
from tests.test_motor import nueva_visita


def test_informe_vista_previa_y_texto(proyecto, entorno, tmp_path, monkeypatch):
    config = cargar_config(proyecto, entorno)
    v = nueva_visita(config)
    monkeypatch.setattr(cli, "construir_recolector", lambda c: recolector_offline(tmp_path, alertas=[]))
    runner = CliRunner()
    salida = tmp_path / "salida.html"
    r = runner.invoke(cli.app, ["informe", v.id, "--hito", "12", "--vista-previa", str(salida), "--ahora", "2026-10-03T21:17-03:00", "--base", str(proyecto)])
    assert r.exit_code == 0, r.output
    assert "Informe de visita — 12 h antes" in salida.read_text(encoding="utf-8")
    assert salida.with_suffix(".txt").exists()
    r = runner.invoke(cli.app, ["informe", v.id, "--hito", "24", "--ahora", "2026-10-03T09:17-03:00", "--base", str(proyecto)])
    assert r.exit_code == 0 and "Asunto: 🐝 Visita" in r.output and "RESUMEN DE LA VENTANA" in r.output
    r = runner.invoke(cli.app, ["informe", "no-existe", "--base", str(proyecto)])
    assert r.exit_code == 1


def test_probar_fuentes(proyecto, tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "construir_recolector", lambda c: recolector_offline(tmp_path, alertas=[]))
    with time_machine.travel(datetime(2026, 10, 4, 0, 17, tzinfo=UTC)):
        r = CliRunner().invoke(cli.app, ["probar-fuentes", "--base", str(proyecto)])
    assert r.exit_code == 0, r.output
    assert "produccion_miel · smn_wrf: OK (6/6 horas con temperatura; ciclo 03/10 12 UTC)" in r.output
    assert "produccion_miel · metno: OK" in r.output
    assert "smn_cap: OK (0 alertas vigentes para el punto)" in r.output
    assert "correo:" in r.output


def test_probar_fuentes_informa_fallas(proyecto, tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "construir_recolector", lambda c: recolector_offline(tmp_path, alertas=[], alertas_disponibles=False))
    with time_machine.travel(datetime(2026, 10, 4, 0, 17, tzinfo=UTC)):
        r = CliRunner().invoke(cli.app, ["probar-fuentes", "--base", str(proyecto)])
    assert r.exit_code == 1 and "smn_cap: NO DISPONIBLE" in r.output


def test_publicar_y_config_invalida(proyecto, tmp_path):
    runner = CliRunner()
    r = runner.invoke(cli.app, ["publicar", "--ahora", "2026-10-03T10:00-03:00", "--base", str(proyecto)])
    assert r.exit_code == 0 and "publico/" in r.output
    r = runner.invoke(cli.app, ["listar", "--base", str(tmp_path)])
    assert r.exit_code == 2 and "Error de configuración" in r.output
