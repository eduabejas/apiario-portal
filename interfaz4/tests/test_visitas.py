import pytest
import yaml

from interfaz4.modelos import Visita
from interfaz4.visitas.archivo_yaml import RepositorioYAML
from interfaz4.visitas.base import ErrorVisitas, registrar_visita
from tests.conftest import local

AHORA = local("2026-10-03T10:00")


def repo(config):
    return RepositorioYAML(config.rutas.visitas_yaml)


def registrar(config, **kw):
    datos = dict(apiario="produccion_miel", fecha="2026-10-10", desde="09:00", hasta="13:00", responsable="Nombre Apellido", ahora=AHORA)
    datos.update(kw)
    return registrar_visita(config, repo(config), **datos)


def test_registrar_genera_ids_correlativos(config):
    v1 = registrar(config)
    v2 = registrar(config, desde="15:00", hasta="17:00")
    otra_fecha = registrar(config, fecha="2026-10-11")
    assert v1.id == "2026-10-10-produccion_miel-01"
    assert v2.id == "2026-10-10-produccion_miel-02"
    assert otra_fecha.id == "2026-10-11-produccion_miel-01"
    assert [v.id for v in repo(config).listar()] == [v1.id, v2.id, otra_fecha.id]
    assert v1.registrada == AHORA and v1.canales == ["correo"]


def test_yaml_legible_y_estable(config):
    registrar(config, notas="Revisión de núcleos", chat=True)
    texto = config.rutas.visitas_yaml.read_text(encoding="utf-8")
    assert texto.startswith("# Visitas registradas")
    assert "Revisión de núcleos" in texto  # unicode sin escapar
    crudo = yaml.safe_load(texto)["visitas"][0]
    assert crudo["hasta"] == "13:00" and crudo["fecha"] == "2026-10-10"  # quedan como texto
    assert crudo["canales"] == ["correo", "google_chat"]
    assert "correo" not in crudo  # sin correo explícito no se escribe


@pytest.mark.parametrize(
    "kw,mensaje",
    [
        ({"apiario": "cria_reinas"}, "Apiario desconocido"),
        ({"fecha": "10/10/2026"}, "Fecha inválida"),
        ({"desde": "13:00", "hasta": "09:00"}, "posterior"),
        ({"desde": "9am"}, "Hora inválida"),
        ({"fecha": "2026-10-03", "desde": "08:00", "hasta": "09:00"}, "debe ser futura"),
        ({"correo": "no-es-correo"}, "correo"),
    ],
)
def test_validaciones_de_registro(config, kw, mensaje):
    with pytest.raises(ErrorVisitas, match=mensaje):
        registrar(config, **kw)
    assert repo(config).listar() == []


def test_cancelar(config):
    v = registrar(config)
    assert repo(config).cancelar(v.id).estado == "cancelada"
    assert repo(config).obtener(v.id).estado == "cancelada"
    with pytest.raises(ErrorVisitas, match="ya estaba cancelada"):
        repo(config).cancelar(v.id)
    with pytest.raises(ErrorVisitas, match="No existe"):
        repo(config).cancelar("inexistente")


def test_yaml_invalido_o_ids_repetidos(config):
    ruta = config.rutas.visitas_yaml
    ruta.write_text("visitas:\n  - id: x\n    apiario: produccion_miel\n    fecha: 2026-10-10\n    desde: '13:00'\n    hasta: '09:00'\n", encoding="utf-8")
    with pytest.raises(ErrorVisitas, match="visita #1"):
        repo(config).listar()
    v = {"apiario": "produccion_miel", "fecha": "2026-10-10", "desde": "09:00", "hasta": "13:00"}
    ruta.write_text(yaml.safe_dump({"visitas": [{"id": "a", **v}, {"id": "a", **v}]}), encoding="utf-8")
    with pytest.raises(ErrorVisitas, match="repetidos"):
        repo(config).listar()


def test_yaml_escrito_a_mano_con_horas_sin_comillas(config):
    config.rutas.visitas_yaml.write_text(
        "visitas:\n  - id: manual-1\n    apiario: produccion_miel\n    fecha: 2026-10-10\n    desde: 09:00\n    hasta: 13:00\n",
        encoding="utf-8",
    )
    [v] = repo(config).listar()
    assert isinstance(v, Visita) and v.hasta.hour == 13
