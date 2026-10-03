"""Interfaz común de los repositorios de visitas y reglas de registro."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from datetime import date, datetime

from pydantic import ValidationError

from interfaz4 import tiempo
from interfaz4.config import Config, ErrorConfig
from interfaz4.modelos import Visita


class ErrorVisitas(Exception):
    """Visita inválida o inexistente (mensaje apto para mostrar al usuario)."""


def _mensaje_validacion(e: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(x) for x in err['loc']) or 'visita'}: {err['msg']}" for err in e.errors())


class RepositorioVisitas(ABC):
    @abstractmethod
    def listar(self) -> list[Visita]: ...

    @abstractmethod
    def guardar(self, visitas: list[Visita]) -> None: ...

    def obtener(self, visita_id: str) -> Visita:
        for v in self.listar():
            if v.id == visita_id:
                return v
        raise ErrorVisitas(f"No existe la visita {visita_id!r}")

    def nuevo_id(self, fecha: date, apiario: str) -> str:
        prefijo = f"{fecha.isoformat()}-{apiario}-"
        usados = [
            int(m.group(1))
            for v in self.listar()
            if (m := re.fullmatch(re.escape(prefijo) + r"(\d+)", v.id))
        ]
        return f"{prefijo}{(max(usados) + 1) if usados else 1:02d}"

    def agregar(self, visita: Visita) -> Visita:
        visitas = self.listar()
        if any(v.id == visita.id for v in visitas):
            raise ErrorVisitas(f"Ya existe una visita con id {visita.id!r}")
        visitas.append(visita)
        self.guardar(visitas)
        return visita

    def cancelar(self, visita_id: str) -> Visita:
        visitas = self.listar()
        for i, v in enumerate(visitas):
            if v.id == visita_id:
                if v.estado == "cancelada":
                    raise ErrorVisitas(f"La visita {visita_id} ya estaba cancelada")
                visitas[i] = v.model_copy(update={"estado": "cancelada"})
                self.guardar(visitas)
                return visitas[i]
        raise ErrorVisitas(f"No existe la visita {visita_id!r}")


def registrar_visita(
    config: Config,
    repo: RepositorioVisitas,
    *,
    apiario: str,
    fecha: str | date,
    desde: str,
    hasta: str,
    responsable: str,
    ahora: datetime,
    correo: str | None = None,
    chat: bool = False,
    notas: str | None = None,
    origen: str | None = None,
    visita_id: str | None = None,
) -> Visita:
    """Valida y agrega una visita: apiario existente, hasta > desde, inicio
    futuro, id único. El correo es el canal obligatorio; Google Chat es extra."""
    try:
        config.apiario(apiario)
    except ErrorConfig as e:
        raise ErrorVisitas(str(e)) from e
    try:
        fecha_d = fecha if isinstance(fecha, date) else date.fromisoformat(str(fecha).strip())
    except ValueError as e:
        raise ErrorVisitas(f"Fecha inválida {fecha!r}: usar AAAA-MM-DD") from e
    try:
        visita = Visita(
            id=visita_id or repo.nuevo_id(fecha_d, apiario),
            apiario=apiario,
            fecha=fecha_d,
            desde=desde,
            hasta=hasta,
            responsable=responsable or "",
            correo=correo,
            canales=["correo", "google_chat"] if chat else ["correo"],
            notas=notas or None,
            origen=origen,
            registrada=tiempo.a_local(ahora).replace(second=0, microsecond=0),
        )
    except ValidationError as e:
        raise ErrorVisitas(_mensaje_validacion(e)) from e
    if visita.inicio <= ahora:
        raise ErrorVisitas(
            f"La visita debe ser futura: {tiempo.fmt_momento(visita.inicio)} ya pasó "
            f"(ahora: {tiempo.fmt_momento(ahora)})"
        )
    return repo.agregar(visita)
