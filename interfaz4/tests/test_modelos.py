from datetime import date, time

import pytest
from pydantic import ValidationError

from interfaz4.modelos import Apiario, Visita
from tests.conftest import local


def visita(**cambios):
    datos = {
        "id": "2026-10-10-produccion_miel-01",
        "apiario": "produccion_miel",
        "fecha": "2026-10-10",
        "desde": "09:00",
        "hasta": "13:00",
        "responsable": "Nombre Apellido",
    }
    datos.update(cambios)
    return Visita(**datos)


def test_visita_valida_y_ventana_local():
    v = visita()
    assert v.fecha == date(2026, 10, 10)
    assert v.desde == time(9, 0)
    assert v.inicio == local("2026-10-10T09:00")
    assert v.fin == local("2026-10-10T13:00")
    assert v.canales == ["correo"]
    assert v.estado == "planificada"


def test_hasta_debe_ser_posterior_a_desde():
    with pytest.raises(ValidationError, match="posterior"):
        visita(desde="13:00", hasta="09:00")
    with pytest.raises(ValidationError):
        visita(desde="09:00", hasta="09:00")


def test_hora_sexagesimal_de_yaml():
    # PyYAML (YAML 1.1) convierte 13:00 sin comillas en 780.
    assert visita(hasta=780).hasta == time(13, 0)


def test_id_invalido():
    with pytest.raises(ValidationError):
        visita(id="con espacios")
    with pytest.raises(ValidationError):
        visita(id="")


def test_canales_sin_duplicados_y_no_vacios():
    assert visita(canales=["correo", "correo", "google_chat"]).canales == ["correo", "google_chat"]
    with pytest.raises(ValidationError):
        visita(canales=[])
    with pytest.raises(ValidationError):
        visita(canales=["sms"])


def test_correo_opcional_validado():
    assert visita(correo=" a@b.com , c@d.org").correo == "a@b.com, c@d.org"
    assert visita(correo="").correo is None
    with pytest.raises(ValidationError):
        visita(correo="no-es-correo")


def test_campos_desconocidos_se_rechazan():
    with pytest.raises(ValidationError):
        visita(color="rojo")


def test_como_yaml_es_estable():
    datos = visita(notas="Revisión de núcleos").como_yaml()
    assert datos["desde"] == "09:00" and datos["hasta"] == "13:00"
    assert datos["fecha"] == "2026-10-10"
    assert "correo" not in datos
    assert Visita(**datos) == visita(notas="Revisión de núcleos")


def test_apiario_coord_4_decimales():
    a = Apiario(id="x", nombre="X", lat=-34.889180362505506, lon=-57.82789829443907)
    assert a.coord_4 == (-34.8892, -57.8279)
