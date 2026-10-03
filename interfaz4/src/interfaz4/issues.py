"""Ida humano → motor desde GitHub Issues (formulario de Interfaz 4).

El workflow de registro pasa el evento `issues` (JSON de GITHUB_EVENT_PATH).
Se procesa sin interpolar nada en shell: el cuerpo del issue es texto no
confiable y solo se interpreta como campos del formulario.

Solo se aceptan issues de la cuenta dueña o de colaboradores
(author_association OWNER / MEMBER / COLLABORATOR), para que nadie de afuera
pueda agendar envíos de correo.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

from interfaz4 import tiempo
from interfaz4.config import Config
from interfaz4.estado import momento_hito
from interfaz4.modelos import Visita
from interfaz4.visitas.archivo_yaml import RepositorioYAML
from interfaz4.visitas.base import ErrorVisitas, registrar_visita

ETIQUETA_VISITA = "interfaz4-visita"
ETIQUETA_CANCELAR = "interfaz4-cancelar"
ASOCIACIONES_PERMITIDAS = {"OWNER", "MEMBER", "COLLABORATOR"}
SIN_RESPUESTA = {"_no response_", "none", "-", ""}
MAX_CUERPO = 20_000


@dataclass
class ResultadoIssue:
    procesado: bool  # False = no es un issue de Interfaz 4 (se ignora sin comentar)
    ok: bool = False
    cambios: bool = False  # se modificó datos/visitas.yaml
    cerrar: bool = False
    comentario: str = ""
    visita_id: str | None = None


def _clave(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", " ", sin_tildes).split()[0] if sin_tildes.strip() else ""


def parsear_formulario(cuerpo: str) -> dict[str, str]:
    """Cuerpo de un issue form ('### Etiqueta' + valor) → {clave: valor}.

    La clave es la primera palabra de la etiqueta, sin tildes y en minúsculas
    ('### Fecha (AAAA-MM-DD)' → 'fecha'). '_No response_' → ausente.
    """
    campos: dict[str, str] = {}
    actual: str | None = None
    lineas: list[str] = []

    def cerrar_campo() -> None:
        if actual is not None:
            valor = "\n".join(lineas).strip()
            if valor.lower() not in SIN_RESPUESTA:
                campos[actual] = valor

    for linea in cuerpo[:MAX_CUERPO].replace("\r\n", "\n").split("\n"):
        if linea.startswith("### "):
            cerrar_campo()
            actual, lineas = _clave(linea[4:]), []
        elif actual is not None:
            lineas.append(linea)
    cerrar_campo()
    return campos


def _checkbox_marcado(valor: str | None) -> bool:
    return bool(valor) and bool(re.search(r"-\s*\[[xX]\]", valor or ""))


def tipo_de_issue(issue: dict) -> str | None:
    etiquetas = {(e.get("name") or "") for e in issue.get("labels") or []}
    titulo = (issue.get("title") or "").lower()
    if ETIQUETA_CANCELAR in etiquetas or titulo.startswith("interfaz 4 · cancelar"):
        return "cancelar"
    if ETIQUETA_VISITA in etiquetas or titulo.startswith("interfaz 4 · visita"):
        return "visita"
    return None


def agenda_de_informes(config: Config, visita: Visita, ahora: datetime) -> list[str]:
    """Misma regla que el planificador: de los hitos ya vencidos sale solo el
    más cercano al inicio (enseguida) y los anteriores se omiten."""
    vencidos = [h for h in config.ajustes.hitos_horas if momento_hito(visita.inicio, h) <= ahora]
    inmediato = min(vencidos) if vencidos else None
    lineas = []
    for h in config.ajustes.hitos_horas:
        momento = momento_hito(visita.inicio, h)
        if momento > ahora:
            lineas.append(f"- Informe {h} h: aprox. {tiempo.fmt_momento(momento)} (en la primera ejecución horaria posterior)")
        elif h == inmediato:
            lineas.append(f"- Informe {h} h: su momento ya pasó; sale en la próxima ejecución del motor (en unos minutos)")
        else:
            lineas.append(f"- Informe {h} h: no se envía (su momento ya pasó y sale el de {inmediato} h)")
    return lineas


def _resumen_visita(config: Config, v: Visita) -> list[str]:
    apiario = config.apiario(v.apiario)
    lineas = [
        f"- **Id:** `{v.id}`",
        f"- **Apiario:** {apiario.nombre} ({apiario.localidad})",
        f"- **Visita:** {tiempo.fmt_dia_fecha(v.fecha)} · {tiempo.fmt_hora(v.desde)}–{tiempo.fmt_hora(v.hasta)} (hora Argentina)",
        f"- **Responsable:** {v.responsable or 's/d'}",
        f"- **Canales:** {', '.join('correo' if c == 'correo' else 'Google Chat' for c in v.canales)}",
    ]
    if v.notas:
        lineas.append(f"- **Notas:** {v.notas}")
    return lineas


def procesar_evento(config: Config, evento: dict, ahora: datetime) -> ResultadoIssue:
    issue = evento.get("issue") or {}
    tipo = tipo_de_issue(issue)
    if tipo is None or (issue.get("state") or "open") != "open":
        return ResultadoIssue(procesado=False)
    numero = issue.get("number")
    if (issue.get("author_association") or "").upper() not in ASOCIACIONES_PERMITIDAS:
        return ResultadoIssue(
            procesado=True,
            cerrar=True,
            comentario=(
                "Este formulario agenda envíos de correo del motor de Interfaz 4, así que solo se aceptan "
                "issues de la cuenta dueña del repositorio o de colaboradores. El issue se cierra sin cambios."
            ),
        )
    repo = RepositorioYAML(config.rutas.visitas_yaml)
    campos = parsear_formulario(issue.get("body") or "")
    origen = f"issue #{numero}"
    try:
        if tipo == "visita":
            existente = next((v for v in repo.listar() if v.origen == origen), None)
            if existente:
                return ResultadoIssue(
                    procesado=True,
                    ok=True,
                    cerrar=True,
                    visita_id=existente.id,
                    comentario=f"Esta visita ya estaba registrada como `{existente.id}`. No se hicieron cambios.",
                )
            faltan = [c for c in ("fecha", "desde", "hasta") if not campos.get(c)]
            if faltan:
                raise ErrorVisitas(f"faltan campos obligatorios: {', '.join(faltan)}")
            visita = registrar_visita(
                config,
                repo,
                # Opción del desplegable: "produccion_miel — Apiario de ..." → "produccion_miel"
                apiario=(campos.get("apiario") or next(iter(config.apiarios))).split()[0],
                fecha=campos["fecha"],
                desde=campos["desde"],
                hasta=campos["hasta"],
                responsable=(campos.get("responsable") or "")[:120],
                notas=(campos.get("notas") or "")[:1000] or None,
                chat=_checkbox_marcado(campos.get("canales")),
                origen=origen,
                ahora=ahora,
            )
            comentario = "\n".join(
                [
                    "✅ **Visita registrada.**",
                    "",
                    *_resumen_visita(config, visita),
                    "",
                    "**Informes programados** (contexto meteorológico, sin interpretación):",
                    *agenda_de_informes(config, visita, ahora),
                    "",
                    "Para cancelarla, usá el botón *Cancelar* en Interfaz 4 o abrí un issue "
                    f"\"Interfaz 4 · Cancelar visita\" con el id `{visita.id}`.",
                ]
            )
            return ResultadoIssue(procesado=True, ok=True, cambios=True, cerrar=True, comentario=comentario, visita_id=visita.id)
        visita_id = (campos.get("visita") or campos.get("id") or "").strip().strip("`")
        if not visita_id:
            raise ErrorVisitas("falta el id de la visita a cancelar")
        visita = repo.cancelar(visita_id)
        return ResultadoIssue(
            procesado=True,
            ok=True,
            cambios=True,
            cerrar=True,
            visita_id=visita.id,
            comentario="\n".join(["🗑️ **Visita cancelada.** No se enviarán más informes.", "", *_resumen_visita(config, visita)]),
        )
    except ErrorVisitas as e:
        return ResultadoIssue(
            procesado=True,
            ok=False,
            comentario=(
                f"⚠️ **No se pudo procesar:** {e}\n\n"
                "Editá el issue para corregir los datos (se vuelve a procesar al guardar) o cerralo."
            ),
        )
