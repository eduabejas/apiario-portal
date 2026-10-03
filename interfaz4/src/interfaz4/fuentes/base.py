"""Interfaz común de las fuentes de pronóstico."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import UTC, datetime
from typing import ClassVar, Literal

from interfaz4 import tiempo
from interfaz4.modelos import Apiario, SerieFuente

Reloj = Callable[[], datetime]
Variables = Literal["todas", "precipitacion"]


def reloj_real() -> datetime:
    return datetime.now(UTC)


class ErrorFuente(Exception):
    """Falla de una fuente (red, HTTP, formato). El informe sigue sin ella."""


class Fuente(ABC):
    """Una fuente devuelve, para un apiario y un rango de filas horarias
    [inicio, fin) en hora local, una SerieFuente normalizada.

    Nunca lanza por fallas de la fuente: las deja en `SerieFuente.errores`
    para que el informe muestre "s/d" y siga con las demás.
    """

    nombre: ClassVar[str]
    etiqueta: ClassVar[str]

    def __init__(self, reloj: Reloj = reloj_real) -> None:
        self.reloj = reloj

    def serie_vacia(self, inicio: datetime, fin: datetime, error: str | None = None) -> SerieFuente:
        from interfaz4.modelos import PuntoHorario

        puntos = [PuntoHorario(hora_local=h) for h in tiempo.rango_horas(inicio, fin)]
        return SerieFuente(
            fuente=self.nombre,  # type: ignore[arg-type]
            obtenido_utc=self.reloj(),
            puntos=puntos,
            errores=[error] if error else [],
        )

    @abstractmethod
    def obtener(
        self, apiario: Apiario, inicio: datetime, fin: datetime, variables: Variables = "todas"
    ) -> SerieFuente:
        """Filas H con inicio <= H < fin (inicio y fin en punto, hora local).

        Con variables="precipitacion" la fuente puede limitarse a la lluvia
        (lo usa el tramo previo); las demás columnas quedan en None.
        """
