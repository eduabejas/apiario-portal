"""Visitas en datos/visitas.yaml (MVP de la spec)."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from interfaz4.modelos import Visita
from interfaz4.visitas.base import ErrorVisitas, RepositorioVisitas, _mensaje_validacion

ENCABEZADO = """\
# Visitas registradas (hora local de Argentina). Se agregan desde Interfaz 4
# (issue de GitHub), con la CLI (`interfaz4 planificar ...`) o editando este
# archivo. El repo es público: no pongas correos acá; se resuelven desde los
# secretos CORREOS_RESPONSABLES / CORREO_DESTINO_POR_DEFECTO.
"""


class RepositorioYAML(RepositorioVisitas):
    def __init__(self, ruta: Path) -> None:
        self.ruta = ruta

    def listar(self) -> list[Visita]:
        if not self.ruta.exists():
            return []
        try:
            datos = yaml.safe_load(self.ruta.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise ErrorVisitas(f"{self.ruta}: YAML inválido ({e})") from e
        crudas = datos.get("visitas") or [] if isinstance(datos, dict) else None
        if not isinstance(crudas, list):
            raise ErrorVisitas(f"{self.ruta}: se espera una lista bajo 'visitas:'")
        visitas: list[Visita] = []
        for i, cruda in enumerate(crudas):
            try:
                visitas.append(Visita(**(cruda or {})))
            except (ValidationError, TypeError) as e:
                detalle = _mensaje_validacion(e) if isinstance(e, ValidationError) else str(e)
                raise ErrorVisitas(f"{self.ruta}: visita #{i + 1} ({(cruda or {}).get('id', 'sin id')}): {detalle}") from e
        ids = [v.id for v in visitas]
        repetidos = sorted({x for x in ids if ids.count(x) > 1})
        if repetidos:
            raise ErrorVisitas(f"{self.ruta}: ids repetidos: {', '.join(repetidos)}")
        return visitas

    def guardar(self, visitas: list[Visita]) -> None:
        cuerpo = yaml.safe_dump(
            {"visitas": [v.como_yaml() for v in visitas]},
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=100,
        )
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta.with_suffix(".yaml.tmp")
        temporal.write_text(ENCABEZADO + cuerpo, encoding="utf-8")
        temporal.replace(self.ruta)
