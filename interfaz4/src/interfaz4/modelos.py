"""Modelos de datos (pydantic v2): apiarios, visitas, series normalizadas,
alertas y estado de envíos."""

from __future__ import annotations

import re
from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from interfaz4 import tiempo

Canal = Literal["correo", "google_chat"]
CANALES: tuple[str, ...] = ("correo", "google_chat")
EstadoVisita = Literal["planificada", "cancelada"]
NombreFuente = Literal["smn_wrf", "metno", "open_meteo", "ecmwf_ens"]
EstadoHito = Literal["pendiente", "enviado", "parcial", "error", "omitido", "vencido_sin_envio"]

PATRON_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
PATRON_CORREO = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")


def correo_valido(valor: str) -> bool:
    return bool(PATRON_CORREO.match(valor.strip()))


class Apiario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    nombre: str
    localidad: str = ""
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)

    @property
    def coord_4(self) -> tuple[float, float]:
        """Coordenada redondeada a 4 decimales (MET Norway / Open-Meteo)."""
        return (round(self.lat, 4), round(self.lon, 4))


class Visita(BaseModel):
    """Visita registrada por el/la apicultor/a (hora local de Argentina)."""

    model_config = ConfigDict(extra="forbid")

    id: str
    apiario: str
    fecha: date
    desde: time
    hasta: time
    responsable: str = Field(default="", max_length=120)
    correo: str | None = None
    canales: list[Canal] = Field(default_factory=lambda: ["correo"])
    estado: EstadoVisita = "planificada"
    notas: str | None = Field(default=None, max_length=1000)
    origen: str | None = Field(default=None, max_length=120)
    registrada: datetime | None = None

    @field_validator("id")
    @classmethod
    def _id(cls, v: str) -> str:
        if not PATRON_ID.match(v):
            raise ValueError("id inválido: usar letras, números, '-', '_' o '.' (máx. 80)")
        return v

    @field_validator("desde", "hasta", mode="before")
    @classmethod
    def _hora(cls, v: object) -> time:
        return tiempo.parsear_hora(v)

    @field_validator("correo")
    @classmethod
    def _correo(cls, v: str | None) -> str | None:
        if v is None or not v.strip():
            return None
        for parte in v.split(","):
            if not correo_valido(parte):
                raise ValueError(f"correo inválido: {parte.strip()!r}")
        return ", ".join(p.strip() for p in v.split(","))

    @field_validator("canales")
    @classmethod
    def _canales(cls, v: list[str]) -> list[str]:
        unicos = list(dict.fromkeys(v))
        if not unicos:
            raise ValueError("la visita necesita al menos un canal")
        return unicos

    @field_validator("notas", "responsable", "origen")
    @classmethod
    def _texto(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v

    @model_validator(mode="after")
    def _ventana(self) -> Visita:
        if self.hasta <= self.desde:
            raise ValueError("'hasta' debe ser posterior a 'desde' (misma fecha)")
        return self

    @property
    def inicio(self) -> datetime:
        return tiempo.localizar(self.fecha, self.desde)

    @property
    def fin(self) -> datetime:
        return tiempo.localizar(self.fecha, self.hasta)

    def como_yaml(self) -> dict:
        """Representación estable para datos/visitas.yaml (horas entre comillas)."""
        datos: dict = {
            "id": self.id,
            "apiario": self.apiario,
            "fecha": self.fecha.isoformat(),
            "desde": tiempo.fmt_hora(self.desde),
            "hasta": tiempo.fmt_hora(self.hasta),
            "responsable": self.responsable,
        }
        if self.correo:
            datos["correo"] = self.correo
        datos["canales"] = list(self.canales)
        datos["estado"] = self.estado
        if self.notas:
            datos["notas"] = self.notas
        if self.origen:
            datos["origen"] = self.origen
        if self.registrada:
            datos["registrada"] = tiempo.a_local(self.registrada).isoformat(timespec="minutes")
        return datos


# ----------------------------------------------------------------- series


class PuntoHorario(BaseModel):
    """Fila H = intervalo [H, H+1h) en hora local."""

    hora_local: datetime
    temp_c: float | None = None  # instantáneo en H
    hr_pct: float | None = None  # instantáneo en H
    viento_kmh: float | None = None  # instantáneo en H
    viento_dir_grados: float | None = None
    viento_dir_cardinal: str | None = None  # 16 rumbos
    rafaga_kmh: float | None = None  # máximo del intervalo [H, H+1h)
    precip_mm: float | None = None  # acumulado del intervalo [H, H+1h)
    prob_precip_pct: float | None = None  # probabilidad para el intervalo [H, H+1h)


class SerieFuente(BaseModel):
    fuente: NombreFuente
    emitido_utc: datetime | None = None  # ciclo del modelo o actualización del producto
    obtenido_utc: datetime
    puntos: list[PuntoHorario] = Field(default_factory=list)
    errores: list[str] = Field(default_factory=list)
    detalle_emision: str | None = None  # p. ej. "ciclo 09/10 06 UTC"

    def punto(self, hora: datetime) -> PuntoHorario | None:
        for p in self.puntos:
            if p.hora_local == hora:
                return p
        return None


# ---------------------------------------------------------------- alertas


class Alerta(BaseModel):
    """Alerta CAP del SMN, copiada textual (sin resumir ni reescribir)."""

    identificador: str
    enviada: datetime | None = None
    evento: str = ""
    severidad: str | None = None
    urgencia: str | None = None
    certeza: str | None = None
    inicio: datetime | None = None  # onset (o effective si falta)
    expira: datetime | None = None
    titular: str | None = None
    descripcion: str | None = None
    instruccion: str | None = None
    areas: list[str] = Field(default_factory=list)
    remitente: str | None = None
    url: str | None = None


class ResultadoAlertas(BaseModel):
    disponible: bool
    alertas: list[Alerta] = Field(default_factory=list)
    errores: list[str] = Field(default_factory=list)
    obtenido_utc: datetime | None = None


# --------------------------------------------------------- estado de envíos


class RegistroHito(BaseModel):
    model_config = ConfigDict(extra="ignore")

    estado: EstadoHito = "pendiente"
    momento: datetime | None = None
    canales: dict[str, str] = Field(default_factory=dict)
    snapshot: str | None = None
    detalle: str | None = None
