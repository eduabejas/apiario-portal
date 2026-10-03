import json

import pytest
from typer.testing import CliRunner

from interfaz4.issues import parsear_formulario, procesar_evento
from interfaz4.visitas.archivo_yaml import RepositorioYAML
from tests.conftest import local

AHORA = local("2026-10-03T10:00")

CUERPO = """### Apiario

produccion_miel — Apiario de producción melífera

### Fecha (AAAA-MM-DD)

2026-10-10

### Desde (HH:MM, hora Argentina)

09:00

### Hasta (HH:MM, hora Argentina)

13:00

### Responsable

Eduardo Mendoza

### Notas (opcional)

_No response_

### Canales

- [ ] También por Google Chat (requiere Google Workspace)
"""


def evento(cuerpo=CUERPO, asociacion="OWNER", etiquetas=("interfaz4-visita",), numero=7, estado="open", titulo="Interfaz 4 · Visita 2026-10-10 09:00–13:00"):
    return {
        "action": "opened",
        "issue": {
            "number": numero,
            "title": titulo,
            "body": cuerpo,
            "state": estado,
            "author_association": asociacion,
            "user": {"login": "eduabejas"},
            "labels": [{"name": e} for e in etiquetas],
        },
    }


def test_parsear_formulario():
    campos = parsear_formulario(CUERPO)
    assert campos["apiario"].startswith("produccion_miel")
    assert campos["fecha"] == "2026-10-10" and campos["desde"] == "09:00" and campos["hasta"] == "13:00"
    assert campos["responsable"] == "Eduardo Mendoza"
    assert "notas" not in campos  # _No response_
    assert campos["canales"].startswith("- [ ]")


def test_registra_visita_desde_issue(config):
    r = procesar_evento(config, evento(), AHORA)
    assert r.procesado and r.ok and r.cambios and r.cerrar
    assert r.accion == "registrar"
    assert r.visita_id == "2026-10-10-produccion_miel-01"
    [v] = RepositorioYAML(config.rutas.visitas_yaml).listar()
    assert v.origen == "issue #7" and v.canales == ["correo"] and v.notas is None
    assert "✅ **Visita registrada.**" in r.comentario
    assert "Informe 24 h: aprox. viernes 09/10/2026 09:00" in r.comentario
    assert "Informe 12 h: aprox. viernes 09/10/2026 21:00" in r.comentario


def test_reprocesar_el_mismo_issue_no_duplica(config):
    procesar_evento(config, evento(), AHORA)
    r = procesar_evento(config, evento(), AHORA)
    assert r.ok and not r.cambios and "ya estaba registrada" in r.comentario
    assert len(RepositorioYAML(config.rutas.visitas_yaml).listar()) == 1


def test_google_chat_marcado(config):
    cuerpo = CUERPO.replace("- [ ] También", "- [X] También")
    procesar_evento(config, evento(cuerpo), AHORA)
    [v] = RepositorioYAML(config.rutas.visitas_yaml).listar()
    assert v.canales == ["correo", "google_chat"]


def test_visita_cercana_avisa_que_solo_va_el_de_12(config):
    r = procesar_evento(config, evento(), local("2026-10-09T23:00"))
    assert "Informe 24 h: no se envía (su momento ya pasó y sale el de 12 h)" in r.comentario
    assert "Informe 12 h: su momento ya pasó; sale en la próxima ejecución del motor" in r.comentario


def test_visita_entre_24_y_12_h_manda_ya_el_de_24_y_luego_el_de_12(config):
    r = procesar_evento(config, evento(), local("2026-10-09T15:00"))
    assert "Informe 24 h: su momento ya pasó; sale en la próxima ejecución del motor" in r.comentario
    assert "Informe 12 h: aprox. viernes 09/10/2026 21:00" in r.comentario


@pytest.mark.parametrize("asociacion", ["NONE", "CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR", ""])
def test_rechaza_autores_externos(config, asociacion):
    r = procesar_evento(config, evento(asociacion=asociacion), AHORA)
    assert r.procesado and not r.ok and not r.cambios and r.cerrar
    assert "colaboradores" in r.comentario
    assert RepositorioYAML(config.rutas.visitas_yaml).listar() == []


def test_ignora_issues_ajenos_o_cerrados(config):
    assert not procesar_evento(config, evento(etiquetas=(), titulo="Bug en la bitácora"), AHORA).procesado
    assert not procesar_evento(config, evento(estado="closed"), AHORA).procesado


def test_titulo_sin_etiqueta_igual_se_reconoce(config):
    assert procesar_evento(config, evento(etiquetas=()), AHORA).ok


@pytest.mark.parametrize(
    "reemplazo,mensaje",
    [
        (("2026-10-10", "_No response_"), "faltan campos obligatorios: fecha"),
        (("13:00", "08:00"), "posterior"),
        (("2026-10-10", "2026-10-01"), "debe ser futura"),
        (("produccion_miel — Apiario de producción melífera", "cria_reinas"), "Apiario desconocido"),
    ],
)
def test_errores_se_comentan_y_el_issue_queda_abierto(config, reemplazo, mensaje):
    r = procesar_evento(config, evento(CUERPO.replace(*reemplazo)), AHORA)
    assert r.procesado and not r.ok and not r.cerrar and not r.cambios
    assert mensaje in r.comentario and "Editá el issue" in r.comentario


def test_cancelar_desde_issue(config):
    procesar_evento(config, evento(), AHORA)
    cuerpo = "### Visita (id)\n\n2026-10-10-produccion_miel-01\n\n### Motivo (opcional)\n\nLluvia\n"
    r = procesar_evento(config, evento(cuerpo, etiquetas=("interfaz4-cancelar",), numero=8, titulo="Interfaz 4 · Cancelar visita"), AHORA)
    assert r.ok and r.cambios and r.accion == "cancelar" and "Visita cancelada" in r.comentario
    assert RepositorioYAML(config.rutas.visitas_yaml).obtener("2026-10-10-produccion_miel-01").estado == "cancelada"
    r = procesar_evento(config, evento("### Visita (id)\n\nno-existe\n", etiquetas=("interfaz4-cancelar",), numero=9), AHORA)
    assert not r.ok and "No existe" in r.comentario


def test_cli_procesar_issue(proyecto, tmp_path, monkeypatch):
    from interfaz4 import cli

    archivo = tmp_path / "evento.json"
    archivo.write_text(json.dumps(evento()), encoding="utf-8")
    salida_gh = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(salida_gh))
    comentario = tmp_path / "comentario.md"
    r = CliRunner().invoke(
        cli.app,
        ["procesar-issue", "--evento", str(archivo), "--comentario", str(comentario), "--ahora", "2026-10-03T10:00-03:00", "--base", str(proyecto)],
    )
    assert r.exit_code == 0, r.output
    assert "Visita registrada" in comentario.read_text(encoding="utf-8")
    salida = salida_gh.read_text()
    assert "ok=true" in salida and "cambios=true" in salida and "cerrar=true" in salida
    assert "accion=registrar" in salida
    assert "visita_id=2026-10-10-produccion_miel-01" in salida
