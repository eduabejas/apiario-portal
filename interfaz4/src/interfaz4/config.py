"""Carga y validación de configuración (YAML) y secretos (entorno / .env)."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from interfaz4 import tiempo
from interfaz4.modelos import CANALES, Apiario, correo_valido

FUENTES_CONOCIDAS = ("smn_wrf", "metno", "smn_cap", "open_meteo", "ecmwf_ens")
UA_METNO_POR_DEFECTO = "interfaz4-apiarios/0.1 (+https://github.com/eduabejas/apiario-portal)"


class ErrorConfig(Exception):
    """Configuración inválida o incompleta."""


# ------------------------------------------------------------------- rutas


@dataclass(frozen=True)
class Rutas:
    base: Path

    @property
    def config_dir(self) -> Path:
        return self.base / "config"

    @property
    def apiarios_yaml(self) -> Path:
        return self.config_dir / "apiarios.yaml"

    @property
    def ajustes_yaml(self) -> Path:
        return self.config_dir / "ajustes.yaml"

    @property
    def visitas_yaml(self) -> Path:
        return self.base / "datos" / "visitas.yaml"

    @property
    def state_dir(self) -> Path:
        return self.base / "state"

    @property
    def envios_json(self) -> Path:
        return self.state_dir / "envios.json"

    @property
    def cache_grilla_json(self) -> Path:
        return self.state_dir / "cache_grilla.json"

    @property
    def cache_metno_json(self) -> Path:
        return self.state_dir / "cache_metno.json"

    @property
    def snapshots_dir(self) -> Path:
        return self.state_dir / "snapshots"

    @property
    def publico_dir(self) -> Path:
        return self.base / "publico"


# ----------------------------------------------------------------- ajustes


class AjustesFuente(BaseModel):
    model_config = ConfigDict(extra="forbid")
    habilitada: bool = False


class AjustesCanal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    habilitado: bool = False


class AjustesInforme(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incluir_tramo_previo: bool = True
    incluir_comparacion_24_12: bool = True


class AjustesReintentos(BaseModel):
    model_config = ConfigDict(extra="forbid")
    http_intentos: int = Field(default=3, ge=1, le=10)
    http_backoff_seg: list[float] = Field(default_factory=lambda: [2.0, 5.0, 15.0])
    timeout_seg: float = Field(default=30.0, gt=0, le=300)


def _fuentes_por_defecto() -> dict[str, AjustesFuente]:
    return {
        "smn_wrf": AjustesFuente(habilitada=True),
        "metno": AjustesFuente(habilitada=True),
        "smn_cap": AjustesFuente(habilitada=True),
        "open_meteo": AjustesFuente(habilitada=False),
        "ecmwf_ens": AjustesFuente(habilitada=False),
    }


def _canales_por_defecto() -> dict[str, AjustesCanal]:
    return {"correo": AjustesCanal(habilitado=True), "google_chat": AjustesCanal(habilitado=False)}


class Ajustes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hitos_horas: list[int] = Field(default_factory=lambda: [24, 12])
    unidades: dict[str, str] = Field(default_factory=lambda: {"viento": "kmh", "temperatura": "C"})
    fuentes: dict[str, AjustesFuente] = Field(default_factory=_fuentes_por_defecto)
    canales: dict[str, AjustesCanal] = Field(default_factory=_canales_por_defecto)
    informe: AjustesInforme = Field(default_factory=AjustesInforme)
    reintentos: AjustesReintentos = Field(default_factory=AjustesReintentos)

    @field_validator("hitos_horas")
    @classmethod
    def _hitos(cls, v: list[int]) -> list[int]:
        if not v or any(h <= 0 for h in v):
            raise ValueError("hitos_horas debe tener horas positivas")
        return sorted(set(v), reverse=True)

    @field_validator("unidades")
    @classmethod
    def _unidades(cls, v: dict[str, str]) -> dict[str, str]:
        if v.get("viento", "kmh") != "kmh" or v.get("temperatura", "C") != "C":
            raise ValueError("solo se soportan viento en kmh y temperatura en C")
        return v

    @field_validator("fuentes")
    @classmethod
    def _fuentes(cls, v: dict[str, AjustesFuente]) -> dict[str, AjustesFuente]:
        desconocidas = set(v) - set(FUENTES_CONOCIDAS)
        if desconocidas:
            raise ValueError(f"fuentes desconocidas: {sorted(desconocidas)}")
        return {**_fuentes_por_defecto(), **v} if v else _fuentes_por_defecto()

    @field_validator("canales")
    @classmethod
    def _canales(cls, v: dict[str, AjustesCanal]) -> dict[str, AjustesCanal]:
        desconocidos = set(v) - set(CANALES)
        if desconocidos:
            raise ValueError(f"canales desconocidos: {sorted(desconocidos)}")
        return {**_canales_por_defecto(), **v} if v else _canales_por_defecto()

    def fuente_habilitada(self, nombre: str) -> bool:
        return self.fuentes.get(nombre, AjustesFuente()).habilitada

    def canal_habilitado(self, nombre: str) -> bool:
        return self.canales.get(nombre, AjustesCanal()).habilitado


# ---------------------------------------------------------------- secretos


class Secretos(BaseModel):
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_usuario: str | None = None
    smtp_clave_app: str | None = None
    smtp_remitente: str | None = None
    smtp_seguridad: Literal["starttls", "ssl", "ninguna"] = "starttls"
    correo_destino_por_defecto: list[str] = Field(default_factory=list)
    correos_responsables: dict[str, list[str]] = Field(default_factory=dict)
    gchat_webhook_url: str | None = None
    metno_user_agent: str = UA_METNO_POR_DEFECTO

    @property
    def smtp_configurado(self) -> bool:
        return bool(self.smtp_host and self.smtp_usuario and self.smtp_clave_app)


def normalizar_nombre(nombre: str) -> str:
    """Clave para comparar nombres: minúsculas, sin tildes ni espacios extra."""
    import unicodedata

    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


def _lista_correos(texto: str | None, variable: str) -> list[str]:
    if not texto or not texto.strip():
        return []
    correos = [c.strip() for c in texto.replace(";", ",").split(",") if c.strip()]
    malos = [c for c in correos if not correo_valido(c)]
    if malos:
        raise ErrorConfig(f"{variable}: correo(s) inválido(s): {', '.join(malos)}")
    return correos


def _correos_responsables(texto: str | None) -> dict[str, list[str]]:
    """JSON {"Nombre": "correo"} o líneas/';' con 'Nombre=correo[,correo]'."""
    if not texto or not texto.strip():
        return {}
    texto = texto.strip()
    pares: list[tuple[str, str]] = []
    if texto.startswith("{"):
        try:
            datos = json.loads(texto)
        except json.JSONDecodeError as e:
            raise ErrorConfig(f"CORREOS_RESPONSABLES: JSON inválido ({e.msg})") from e
        for k, v in datos.items():
            pares.append((str(k), ",".join(v) if isinstance(v, list) else str(v)))
    else:
        for linea in texto.replace(";", "\n").splitlines():
            if not linea.strip():
                continue
            if "=" not in linea:
                raise ErrorConfig("CORREOS_RESPONSABLES: cada entrada debe ser 'Nombre=correo'")
            nombre, correos = linea.split("=", 1)
            pares.append((nombre, correos))
    return {
        normalizar_nombre(nombre): _lista_correos(correos.replace(" ", ","), "CORREOS_RESPONSABLES")
        for nombre, correos in pares
        if nombre.strip()
    }


def _vacio_a_none(valor: str | None) -> str | None:
    return valor.strip() if valor and valor.strip() else None


def cargar_secretos(entorno: Mapping[str, str]) -> Secretos:
    def env(clave: str) -> str | None:
        return _vacio_a_none(entorno.get(clave))

    puerto_txt = env("SMTP_PORT") or "587"
    try:
        puerto = int(puerto_txt)
    except ValueError as e:
        raise ErrorConfig(f"SMTP_PORT inválido: {puerto_txt!r}") from e
    seguridad = (env("SMTP_SEGURIDAD") or ("ssl" if puerto == 465 else "starttls")).lower()
    if seguridad not in ("starttls", "ssl", "ninguna"):
        raise ErrorConfig("SMTP_SEGURIDAD debe ser starttls, ssl o ninguna")
    return Secretos(
        smtp_host=env("SMTP_HOST") or "smtp.gmail.com",
        smtp_port=puerto,
        smtp_usuario=env("SMTP_USUARIO"),
        # Google muestra la contraseña de aplicación en grupos de 4 con espacios.
        smtp_clave_app=(env("SMTP_CLAVE_APP") or "").replace(" ", "") or None,
        smtp_remitente=env("SMTP_REMITENTE"),
        smtp_seguridad=seguridad,
        correo_destino_por_defecto=_lista_correos(env("CORREO_DESTINO_POR_DEFECTO"), "CORREO_DESTINO_POR_DEFECTO"),
        correos_responsables=_correos_responsables(env("CORREOS_RESPONSABLES")),
        gchat_webhook_url=env("GCHAT_WEBHOOK_URL"),
        metno_user_agent=env("METNO_USER_AGENT") or UA_METNO_POR_DEFECTO,
    )


def leer_dotenv(ruta: Path) -> dict[str, str]:
    """Parser mínimo de .env: CLAVE=valor, comentarios con #, comillas opcionales."""
    valores: dict[str, str] = {}
    if not ruta.exists():
        return valores
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, valor = linea.split("=", 1)
        clave = clave.strip().removeprefix("export ").strip()
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        elif " #" in valor:
            valor = valor.split(" #", 1)[0].rstrip()
        valores[clave] = valor
    return valores


# ------------------------------------------------------------------ config


class Config(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    base: Path
    zona_horaria: str = tiempo.ZONA_HORARIA
    apiarios: dict[str, Apiario]
    ajustes: Ajustes
    secretos: Secretos

    @property
    def rutas(self) -> Rutas:
        return Rutas(self.base)

    def apiario(self, clave: str) -> Apiario:
        try:
            return self.apiarios[clave]
        except KeyError:
            raise ErrorConfig(
                f"Apiario desconocido: {clave!r}. Disponibles: {', '.join(sorted(self.apiarios))}"
            ) from None

    def destinatarios(self, correo_visita: str | None, responsable: str) -> list[str]:
        """Correo de la visita → correo del responsable (secreto) → destino por defecto."""
        if correo_visita:
            return [c.strip() for c in correo_visita.split(",") if c.strip()]
        por_responsable = self.secretos.correos_responsables.get(normalizar_nombre(responsable or ""))
        if por_responsable:
            return por_responsable
        return list(self.secretos.correo_destino_por_defecto)


def resolver_base(base: Path | str | None = None) -> Path:
    """--base > INTERFAZ4_BASE > directorio actual (si tiene config/) > raíz del proyecto."""
    candidatos: list[Path] = []
    if base:
        candidatos.append(Path(base))
    elif os.environ.get("INTERFAZ4_BASE"):
        candidatos.append(Path(os.environ["INTERFAZ4_BASE"]))
    else:
        candidatos.append(Path.cwd())
        candidatos.append(Path.cwd() / "interfaz4")
        candidatos.append(Path(__file__).resolve().parents[2])
    for c in candidatos:
        if (c / "config" / "apiarios.yaml").exists():
            return c.resolve()
    raise ErrorConfig(
        "No se encontró config/apiarios.yaml. Ejecutá desde la carpeta interfaz4/ o usá --base."
    )


def _leer_yaml(ruta: Path) -> dict:
    if not ruta.exists():
        raise ErrorConfig(f"Falta el archivo {ruta}")
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ErrorConfig(f"YAML inválido en {ruta}: {e}") from e
    if not isinstance(datos, dict):
        raise ErrorConfig(f"{ruta} debe contener un mapa YAML")
    return datos


def cargar_config(base: Path | str | None = None, entorno: Mapping[str, str] | None = None) -> Config:
    raiz = resolver_base(base)
    rutas = Rutas(raiz)
    if entorno is None:
        entorno = {**leer_dotenv(raiz / ".env"), **os.environ}
    datos_apiarios = _leer_yaml(rutas.apiarios_yaml)
    zona = datos_apiarios.get("zona_horaria", tiempo.ZONA_HORARIA)
    if zona != tiempo.ZONA_HORARIA:
        raise ErrorConfig(f"zona_horaria debe ser {tiempo.ZONA_HORARIA} (llegó {zona!r})")
    crudos = datos_apiarios.get("apiarios") or {}
    if not isinstance(crudos, dict) or not crudos:
        raise ErrorConfig(f"{rutas.apiarios_yaml}: no hay apiarios configurados")
    try:
        apiarios = {clave: Apiario(id=clave, **(valor or {})) for clave, valor in crudos.items()}
        ajustes = Ajustes(**_leer_yaml(rutas.ajustes_yaml))
    except (TypeError, ValueError) as e:
        raise ErrorConfig(f"Configuración inválida: {e}") from e
    return Config(
        base=raiz,
        zona_horaria=zona,
        apiarios=apiarios,
        ajustes=ajustes,
        secretos=cargar_secretos(entorno),
    )
