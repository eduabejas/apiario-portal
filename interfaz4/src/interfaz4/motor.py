"""Ejecución del motor (`interfaz4 ejecutar`): planifica los hitos vencidos,
recolecta datos, genera el informe, lo envía por cada canal y registra el
estado. Una falla en una visita o canal no frena a las demás."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from interfaz4 import tiempo
from interfaz4.config import Config
from interfaz4.estado import EstadoEnvios
from interfaz4.informe.constructor import InformeRenderizado, generar
from interfaz4.informe.recoleccion import DatosInforme, Recolector, construir_recolector, recolectar
from interfaz4.modelos import CANALES, RegistroHito, Visita
from interfaz4.notificar import ErrorEnvio
from interfaz4.notificar.correo_smtp import EnviadorCorreo
from interfaz4.notificar.google_chat import EnviadorGoogleChat
from interfaz4.planificador import Accion, planificar, proximo_momento
from interfaz4.visitas.archivo_yaml import RepositorioYAML

log = logging.getLogger(__name__)


@dataclass
class ResultadoAccion:
    visita_id: str
    hito: int
    tipo: str
    estado: str
    canales: dict[str, str]


@dataclass
class ResultadoEjecucion:
    ahora: datetime
    acciones: list[ResultadoAccion] = field(default_factory=list)
    marcas: list[tuple[str, int, str]] = field(default_factory=list)
    visitas_planificadas: int = 0
    proximo: datetime | None = None  # próximo momento con algo para enviar

    def resumen(self) -> str:
        lineas = [f"Ejecución del {tiempo.fmt_momento(self.ahora)} · visitas planificadas: {self.visitas_planificadas}"]
        for vid, h, est in self.marcas:
            lineas.append(f"- {vid} · hito {h} h → {est}")
        for a in self.acciones:
            canales = ", ".join(f"{c}: {e}" for c, e in a.canales.items())
            lineas.append(f"- {a.visita_id} · informe {a.hito} h ({a.tipo}) → {a.estado} [{canales}]")
        if not self.marcas and not self.acciones:
            lineas.append("- Sin hitos vencidos: no hubo envíos.")
        if self.proximo:
            lineas.append(f"- Próximo envío: {tiempo.fmt_momento(self.proximo)}")
        else:
            lineas.append("- No quedan envíos pendientes.")
        return "\n".join(lineas)


def ruta_snapshot(config: Config, visita_id: str, hito: int) -> Path:
    return config.rutas.snapshots_dir / f"{visita_id}_{hito}.json"


def guardar_snapshot(ruta: Path, datos: DatosInforme) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(datos.model_dump_json(indent=1) + "\n", encoding="utf-8")


def cargar_snapshot(ruta: Path) -> DatosInforme | None:
    if not ruta.exists():
        return None
    try:
        return DatosInforme.model_validate_json(ruta.read_text(encoding="utf-8"))
    except ValueError:
        log.warning("Snapshot ilegible: %s", ruta)
        return None


def informe_previo(config: Config, visita_id: str, hito: int) -> DatosInforme | None:
    """Snapshot del hito anterior más cercano (p. ej. el de 24 h para el de 12 h)."""
    if not config.ajustes.informe.incluir_comparacion_24_12:
        return None
    for h in sorted(x for x in config.ajustes.hitos_horas if x > hito):
        previo = cargar_snapshot(ruta_snapshot(config, visita_id, h))
        if previo is not None:
            return previo
    return None


def renderizar_snapshot(config: Config, datos: DatosInforme) -> InformeRenderizado:
    previo = informe_previo(config, datos.visita.id, datos.hito)
    return generar(datos, previo, config.ajustes.informe.incluir_comparacion_24_12)


class Motor:
    def __init__(
        self,
        config: Config,
        recolector_factory: Callable[[], Recolector] | None = None,
        correo: EnviadorCorreo | None = None,
        chat: EnviadorGoogleChat | None = None,
    ) -> None:
        self.config = config
        self._fabrica = recolector_factory or (lambda: construir_recolector(config))
        self._recolector: Recolector | None = None
        self.correo = correo or EnviadorCorreo(config.secretos)
        self.chat = chat or EnviadorGoogleChat(config.secretos.gchat_webhook_url)

    @property
    def recolector(self) -> Recolector:
        if self._recolector is None:
            self._recolector = self._fabrica()
        return self._recolector

    def enviar(self, visita: Visita, hito: int, render: InformeRenderizado, canales: list[str]) -> dict[str, str]:
        resultado: dict[str, str] = {}
        for canal in canales:
            try:
                if canal == "correo":
                    self.correo.enviar(
                        render.asunto,
                        render.html,
                        render.texto,
                        self.config.destinatarios(visita.correo, visita.responsable),
                    )
                elif canal == "google_chat":
                    self.chat.enviar(render.chat, hilo=f"{visita.id}-{hito}")
                resultado[canal] = "ok"
            except ErrorEnvio as e:
                log.warning("%s · %s h · %s: %s", visita.id, hito, canal, e)
                resultado[canal] = f"error: {e}"
        return resultado

    def procesar(self, accion: Accion, registro: RegistroHito, ahora: datetime) -> RegistroHito:
        v, h = accion.visita, accion.hito
        ruta = ruta_snapshot(self.config, v.id, h)
        datos = cargar_snapshot(ruta) if accion.tipo == "reintentar" else None
        if datos is None:
            datos = recolectar(self.config, v, h, ahora, self.recolector)
            guardar_snapshot(ruta, datos)
        render = renderizar_snapshot(self.config, datos)
        canales = dict(registro.canales) if accion.tipo == "reintentar" else {}
        a_enviar = []
        for canal in CANALES:
            if canal not in v.canales or not self.config.ajustes.canal_habilitado(canal):
                canales[canal] = "deshabilitado"
            elif accion.tipo == "enviar" or canales.get(canal) != "ok":
                a_enviar.append(canal)  # en un reintento, solo lo que no salió
        canales.update(self.enviar(v, h, render, a_enviar))
        intentados = [c for c, e in canales.items() if e != "deshabilitado"]
        ok = [c for c in intentados if canales[c] == "ok"]
        if not intentados:
            estado, detalle = "error", "sin canales habilitados para esta visita"
        else:
            estado = "enviado" if len(ok) == len(intentados) else ("parcial" if ok else "error")
            detalle = None
        return RegistroHito(
            estado=estado,
            momento=ahora,
            canales=canales,
            snapshot=str(ruta.relative_to(self.config.base)),
            detalle=detalle,
        )

    def ejecutar(self, ahora: datetime) -> ResultadoEjecucion:
        ahora = tiempo.a_local(ahora)
        hitos = self.config.ajustes.hitos_horas
        visitas = RepositorioYAML(self.config.rutas.visitas_yaml).listar()
        estado = EstadoEnvios(self.config.rutas.envios_json)
        planificadas = [v for v in visitas if v.estado == "planificada"]
        for v in planificadas:
            estado.asegurar(v.id, hitos)
        plan = planificar(visitas, estado, hitos, ahora)
        resultado = ResultadoEjecucion(ahora=ahora, marcas=plan.marcas, visitas_planificadas=len(planificadas))
        for vid, h, nuevo in plan.marcas:
            estado.actualizar(vid, h, estado.hito(vid, h).model_copy(update={"estado": nuevo, "momento": ahora}))
        for accion in plan.acciones:
            previo = estado.hito(accion.visita.id, accion.hito)
            try:
                registro = self.procesar(accion, previo, ahora)
            except Exception as e:  # no frena al resto de las visitas
                log.exception("Falló el informe %s h de %s", accion.hito, accion.visita.id)
                registro = previo.model_copy(
                    update={"estado": "error", "momento": ahora, "detalle": f"{type(e).__name__}: {e}"[:300]}
                )
            estado.actualizar(accion.visita.id, accion.hito, registro)
            resultado.acciones.append(
                ResultadoAccion(accion.visita.id, accion.hito, accion.tipo, registro.estado, dict(registro.canales))
            )
            estado.guardar()  # persistir después de cada envío
        estado.guardar()
        resultado.proximo = proximo_momento(visitas, estado, hitos, ahora)
        return resultado
