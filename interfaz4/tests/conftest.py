"""Fixtures compartidas: proyecto de prueba con config real y estado vacío."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

import pytest

from interfaz4 import tiempo
from interfaz4.config import cargar_config

RAIZ = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def local(texto: str) -> datetime:
    """'2026-10-04T09:00' → datetime con zona de Argentina."""
    return tiempo.parsear_momento(texto)


@pytest.fixture
def proyecto(tmp_path: Path) -> Path:
    """Copia config/ del repo y deja datos/ y state/ vacíos en un directorio temporal."""
    base = tmp_path / "interfaz4"
    shutil.copytree(RAIZ / "config", base / "config")
    (base / "datos").mkdir(parents=True)
    (base / "datos" / "visitas.yaml").write_text("visitas: []\n", encoding="utf-8")
    (base / "state" / "snapshots").mkdir(parents=True)
    (base / "state" / "envios.json").write_text("{}\n", encoding="utf-8")
    return base


@pytest.fixture
def entorno() -> dict[str, str]:
    return {
        "SMTP_HOST": "localhost",
        "SMTP_PORT": "2525",
        "SMTP_USUARIO": "motor@example.com",
        "SMTP_CLAVE_APP": "abcd efgh ijkl mnop",
        "CORREO_DESTINO_POR_DEFECTO": "apicultor@example.com",
    }


@pytest.fixture
def config(proyecto: Path, entorno: dict[str, str]):
    return cargar_config(proyecto, entorno)
