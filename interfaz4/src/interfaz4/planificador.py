"""Cálculo de hitos vencidos (24 h / 12 h antes) e idempotencia.

Reglas (spec §7):
1. Solo visitas `planificada` con inicio > ahora.
2. Un hito h está vencido si ahora >= inicio − h.
3. Si hay varios vencidos y no enviados, se envía solo el más cercano al
   inicio y los anteriores quedan `omitido`.
4. Si ahora >= inicio, no se envía nada: lo pendiente queda `vencido_sin_envio`.
5. Si un canal falló, en la próxima ejecución se reintenta solo ese canal
   (mientras ese hito siga siendo el vigente).
Tolera ejecuciones demoradas o salteadas del cron.

`proximo_momento` dice cuándo vuelve a haber algo para hacer, para que el
workflow programe la próxima ejecución a esa hora (ver interfaz4-espera.yml).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from interfaz4 import tiempo
from interfaz4.estado import EstadoEnvios, momento_hito
from interfaz4.modelos import Visita

HORAS_REINTENTO = 1


@dataclass
class Accion:
    visita: Visita
    hito: int
    tipo: Literal["enviar", "reintentar"]
    canales: list[str] = field(default_factory=list)


@dataclass
class Plan:
    acciones: list[Accion] = field(default_factory=list)
    marcas: list[tuple[str, int, str]] = field(default_factory=list)  # (visita_id, hito, nuevo_estado)


def canales_fallidos(canales: dict[str, str]) -> list[str]:
    return [c for c, est in canales.items() if est.startswith("error")]


def planificar(visitas: list[Visita], estado: EstadoEnvios, hitos: list[int], ahora: datetime) -> Plan:
    plan = Plan()
    hitos = sorted(set(hitos), reverse=True)
    for v in visitas:
        if v.estado != "planificada":
            continue
        registros = {h: estado.hito(v.id, h) for h in hitos}
        if ahora >= v.inicio:
            for h, r in registros.items():
                if r.estado == "pendiente":
                    plan.marcas.append((v.id, h, "vencido_sin_envio"))
            continue
        vencidos = [h for h in hitos if ahora >= momento_hito(v.inicio, h)]
        if not vencidos:
            continue
        vigente = min(vencidos)
        for h in vencidos:
            if h != vigente and registros[h].estado == "pendiente":
                plan.marcas.append((v.id, h, "omitido"))
        r = registros[vigente]
        if r.estado == "pendiente":
            plan.acciones.append(Accion(v, vigente, "enviar", list(v.canales)))
        elif r.estado in ("parcial", "error"):
            fallidos = canales_fallidos(r.canales) or list(v.canales)
            plan.acciones.append(Accion(v, vigente, "reintentar", fallidos))
    return plan


def proximo_momento(visitas: list[Visita], estado: EstadoEnvios, hitos: list[int], ahora: datetime) -> datetime | None:
    """Próximo momento, posterior a `ahora`, en que una ejecución tiene algo para enviar.

    - Cada hito pendiente que todavía no venció, a su hora.
    - Si el hito vigente quedó con error o parcial, su reintento una hora
      después (si para entonces la visita no empezó).
    Lo que ya venció lo resolvió la ejecución de `ahora`: no se vuelve a
    programar, así una falla que se repite no encadena ejecuciones.
    """
    candidatos: list[datetime] = []
    for v in visitas:
        if v.estado != "planificada" or ahora >= v.inicio:
            continue
        vencidos = []
        for h in hitos:
            momento = momento_hito(v.inicio, h)
            if ahora >= momento:
                vencidos.append(h)
            elif estado.hito(v.id, h).estado == "pendiente":
                candidatos.append(momento)
        if vencidos and estado.hito(v.id, min(vencidos)).estado in ("parcial", "error"):
            reintento = tiempo.sumar_horas(ahora, HORAS_REINTENTO)
            if reintento < v.inicio:
                candidatos.append(reintento)
    return min(candidatos, default=None)
