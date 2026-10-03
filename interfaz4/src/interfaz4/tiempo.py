"""Zona horaria del dominio, redondeos de hora, ventanas y formatos en español.

Todo el dominio trabaja en hora local de Argentina
(`America/Argentina/Buenos_Aires`, UTC−3 sin horario de verano). La
aritmética de horas se hace en UTC y se vuelve a la zona local, así sigue
siendo correcta aunque algún día vuelva el horario de verano.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

ZONA_HORARIA = "America/Argentina/Buenos_Aires"
ZONA_AR = ZoneInfo(ZONA_HORARIA)
UNA_HORA = timedelta(hours=1)

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def ahora() -> datetime:
    """Momento actual en hora local de Argentina."""
    return datetime.now(UTC).astimezone(ZONA_AR)


def _exigir_zona(dt: datetime) -> None:
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"Se esperaba un datetime con zona horaria y llegó {dt!r}")


def a_local(dt: datetime) -> datetime:
    _exigir_zona(dt)
    return dt.astimezone(ZONA_AR)


def a_utc(dt: datetime) -> datetime:
    _exigir_zona(dt)
    return dt.astimezone(UTC)


def localizar(fecha: date, hora: time) -> datetime:
    """Combina fecha y hora (hora local de Argentina) en un datetime con zona."""
    return datetime.combine(fecha, hora.replace(tzinfo=None), tzinfo=ZONA_AR)


def sumar_horas(dt: datetime, horas: float) -> datetime:
    """Suma horas reales (no de reloj) y devuelve el resultado en la zona de `dt`."""
    _exigir_zona(dt)
    return (dt.astimezone(UTC) + timedelta(hours=horas)).astimezone(dt.tzinfo)


def piso_hora(dt: datetime) -> datetime:
    _exigir_zona(dt)
    return dt.replace(minute=0, second=0, microsecond=0)


def techo_hora(dt: datetime) -> datetime:
    piso = piso_hora(dt)
    return piso if piso == dt else sumar_horas(piso, 1)


def rango_horas(inicio: datetime, fin: datetime) -> list[datetime]:
    """Horas en punto H con inicio <= H < fin (inicio debe estar en punto)."""
    if piso_hora(inicio) != inicio:
        raise ValueError(f"El inicio del rango debe estar en punto: {inicio.isoformat()}")
    horas: list[datetime] = []
    h = a_local(inicio)
    while h < fin:
        horas.append(h)
        h = sumar_horas(h, 1)
    return horas


def filas_ventana(desde: datetime, hasta: datetime) -> list[datetime]:
    """Filas horarias de una ventana: de floor(desde) a ceil(hasta) − 1 h.

    Cada fila H representa el intervalo [H, H+1h) en hora local.
    09:00–13:00 → 09, 10, 11, 12 · 09:30–11:15 → 09, 10, 11.
    """
    if hasta <= desde:
        raise ValueError("La ventana debe terminar después de empezar")
    return rango_horas(piso_hora(a_local(desde)), techo_hora(a_local(hasta)))


def parsear_momento(texto: str) -> datetime:
    """ISO 8601; si no trae zona horaria se interpreta como hora de Argentina."""
    valor = texto.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(valor)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZONA_AR)
    return a_local(dt)


def parsear_hora(valor: object) -> time:
    """Acepta "HH:MM", time, o el entero sexagesimal que YAML 1.1 produce con 13:00 sin comillas."""
    if isinstance(valor, time):
        return valor.replace(second=0, microsecond=0, tzinfo=None)
    if isinstance(valor, bool):
        raise ValueError(f"Hora inválida: {valor!r}")
    if isinstance(valor, int):
        if not 0 <= valor < 24 * 60:
            raise ValueError(f"Hora inválida: {valor!r}")
        return time(valor // 60, valor % 60)
    if isinstance(valor, str):
        partes = valor.strip().split(":")
        if len(partes) == 3 and partes[2] == "00":  # "09:00:00" (JSON de pydantic)
            partes = partes[:2]
        if len(partes) == 2 and all(p.isdigit() for p in partes) and len(partes[1]) == 2:
            hh, mm = int(partes[0]), int(partes[1])
            if 0 <= hh < 24 and 0 <= mm < 60:
                return time(hh, mm)
    raise ValueError(f"Hora inválida (se espera HH:MM): {valor!r}")


# ------------------------------------------------------------------ formatos


def fmt_hora(dt: datetime | time) -> str:
    return f"{dt.hour:02d}:{dt.minute:02d}"


def fmt_dd_mm(dt: datetime | date) -> str:
    return f"{dt.day:02d}/{dt.month:02d}"


def fmt_fecha(dt: datetime | date) -> str:
    return f"{dt.day:02d}/{dt.month:02d}/{dt.year}"


def nombre_dia(dt: datetime | date) -> str:
    return DIAS[dt.weekday()]


def fmt_dia_fecha(dt: datetime | date) -> str:
    """'sábado 10/10/2026'."""
    return f"{nombre_dia(dt)} {fmt_fecha(dt)}"


def fmt_momento(dt: datetime) -> str:
    """'viernes 09/10/2026 09:17' (hora local)."""
    local = a_local(dt)
    return f"{fmt_dia_fecha(local)} {fmt_hora(local)}"


def fmt_hora_dia(dt: datetime) -> str:
    """'21:00 del viernes' (hora local)."""
    local = a_local(dt)
    return f"{fmt_hora(local)} del {nombre_dia(local)}"


def fmt_utc_ciclo(dt: datetime) -> str:
    """'09/10 06 UTC' para identificar ciclos de modelos."""
    u = a_utc(dt)
    return f"{u.day:02d}/{u.month:02d} {u.hour:02d} UTC"
