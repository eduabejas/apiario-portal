"""Normalización común a todas las fuentes: unidades, rumbos y convención de
intervalos.

Convención del dominio: la fila H representa el intervalo [H, H+1h) en hora
local. Las variables instantáneas (temperatura, humedad, viento, dirección)
se toman en H. Los acumulados/máximos/probabilidades dependen de la fuente:

| Fuente | Valor en `t` significa | Para la fila H se toma |
|---|---|---|
| SMN WRF `PP` (archivo válido en t) | (t−1h, t] | t = H+1 |
| MET Norway `next_1_hours` | [t, t+1h) | t = H |
| Open-Meteo `precipitation`, `precipitation_probability`, `wind_gusts_10m` | (t−1h, t] | t = H+1 |
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from datetime import datetime
from enum import Enum

from interfaz4 import tiempo
from interfaz4.modelos import PuntoHorario

RUMBOS_16 = ("N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSO", "SO", "OSO", "O", "ONO", "NO", "NNO")
VALOR_RELLENO = 1e19  # _FillValue típico de NetCDF (1e20) y similares


class Convencion(Enum):
    HORA_QUE_TERMINA = "hora_que_termina"  # valor en t = intervalo (t−1h, t]
    HORA_QUE_EMPIEZA = "hora_que_empieza"  # valor en t = intervalo [t, t+1h)


def valor(v: object) -> float | None:
    """float finito o None (NaN, infinitos, valores de relleno, texto)."""
    if v is None or isinstance(v, bool):
        return None
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f) or abs(f) >= VALOR_RELLENO:
        return None
    return f


def ms_a_kmh(v: object) -> float | None:
    f = valor(v)
    return None if f is None else f * 3.6


def grados_a_cardinal(grados: object) -> str | None:
    """Grados (0 = N, sentido horario) → uno de 16 rumbos en español."""
    g = valor(grados)
    if g is None:
        return None
    return RUMBOS_16[int(((g % 360.0) + 11.25) // 22.5) % 16]


def hora_de_fuente(fila: datetime, convencion: Convencion) -> datetime:
    """Timestamp de la fuente del que sale el acumulado de la fila H."""
    return tiempo.sumar_horas(fila, 1) if convencion is Convencion.HORA_QUE_TERMINA else fila


def _redondear(v: float | None, decimales: int) -> float | None:
    return None if v is None else round(v, decimales)


def armar_puntos(
    filas: Iterable[datetime],
    instantaneos: Mapping[datetime, Mapping[str, object]],
    acumulados: Mapping[datetime, Mapping[str, object]],
    convencion: Convencion,
) -> list[PuntoHorario]:
    """Arma las filas H aplicando la convención de intervalos de la fuente.

    `instantaneos[t]` admite: temp_c, hr_pct, viento_kmh, viento_dir_grados.
    `acumulados[t]` admite: precip_mm, rafaga_kmh, prob_precip_pct.
    Las claves son datetimes con zona (se comparan por instante, sin importar
    si vienen en UTC o en hora local). Lo que falta queda en None (s/d).
    """
    puntos: list[PuntoHorario] = []
    for fila in filas:
        h = tiempo.a_local(fila)
        inst = instantaneos.get(h, {})
        acu = acumulados.get(hora_de_fuente(h, convencion), {})
        direccion = valor(inst.get("viento_dir_grados"))
        puntos.append(
            PuntoHorario(
                hora_local=h,
                temp_c=_redondear(valor(inst.get("temp_c")), 2),
                hr_pct=_redondear(valor(inst.get("hr_pct")), 1),
                viento_kmh=_redondear(valor(inst.get("viento_kmh")), 2),
                viento_dir_grados=_redondear(direccion, 1),
                viento_dir_cardinal=grados_a_cardinal(direccion),
                rafaga_kmh=_redondear(valor(acu.get("rafaga_kmh")), 2),
                precip_mm=_redondear(valor(acu.get("precip_mm")), 3),
                prob_precip_pct=_redondear(valor(acu.get("prob_precip_pct")), 1),
            )
        )
    return puntos
