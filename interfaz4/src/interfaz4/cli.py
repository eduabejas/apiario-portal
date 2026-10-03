"""CLI de Interfaz 4 (typer).

    interfaz4 planificar --apiario produccion_miel --fecha 2026-10-10 --desde 09:00 --hasta 13:00 \\
                         --responsable "Nombre" [--correo persona@dominio.com] [--chat] [--notas "..."]
    interfaz4 listar [--todas]
    interfaz4 cancelar <id>
    interfaz4 informe <id> --hito 24 [--enviar | --vista-previa salida.html]
    interfaz4 ejecutar [--ahora 2026-10-09T09:17-03:00]   # --ahora solo para pruebas
    interfaz4 probar-fuentes
    interfaz4 procesar-issue --evento $GITHUB_EVENT_PATH --comentario comentario.md
    interfaz4 publicar
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

from interfaz4 import tiempo
from interfaz4.config import Config, ErrorConfig, cargar_config
from interfaz4.estado import EstadoEnvios, momento_hito
from interfaz4.informe.constructor import generar
from interfaz4.informe.recoleccion import construir_recolector, recolectar
from interfaz4.visitas.archivo_yaml import RepositorioYAML
from interfaz4.visitas.base import ErrorVisitas, registrar_visita

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Interfaz 4 — contexto meteorológico para visitas a apiarios (organiza, no interpreta).",
)

OpcionBase = Annotated[Path | None, typer.Option("--base", help="Carpeta del proyecto (la que tiene config/).")]
OpcionAhora = Annotated[str | None, typer.Option("--ahora", help="Momento simulado ISO 8601 (solo para pruebas).")]


def _config(base: Path | None) -> Config:
    try:
        return cargar_config(base)
    except ErrorConfig as e:
        typer.secho(f"Error de configuración: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2) from e


def _ahora(texto: str | None) -> datetime:
    if not texto:
        return tiempo.ahora()
    try:
        return tiempo.parsear_momento(texto)
    except ValueError as e:
        raise typer.BadParameter(f"--ahora inválido: {texto!r}") from e


def _resumen_github(texto: str) -> None:
    destino = os.environ.get("GITHUB_STEP_SUMMARY")
    if destino:
        with open(destino, "a", encoding="utf-8") as f:
            f.write(texto + "\n")


@app.callback()
def principal(verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Más detalle en los logs.")] = False) -> None:
    logging.basicConfig(
        level=logging.INFO if verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


@app.command()
def planificar(
    apiario: Annotated[str, typer.Option(help="Clave del apiario en config/apiarios.yaml.")],
    fecha: Annotated[str, typer.Option(help="AAAA-MM-DD")],
    desde: Annotated[str, typer.Option(help="HH:MM (hora Argentina)")],
    hasta: Annotated[str, typer.Option(help="HH:MM (hora Argentina)")],
    responsable: Annotated[str, typer.Option(help="Nombre de quien visita.")] = "",
    correo: Annotated[str | None, typer.Option(help="Destinatario(s); si falta se usa el de los secretos.")] = None,
    chat: Annotated[bool, typer.Option("--chat", help="También enviar por Google Chat.")] = False,
    notas: Annotated[str | None, typer.Option(help="Se muestran textuales en el informe.")] = None,
    ahora: OpcionAhora = None,
    base: OpcionBase = None,
) -> None:
    """Registra una visita."""
    config = _config(base)
    momento = _ahora(ahora)
    try:
        v = registrar_visita(
            config,
            RepositorioYAML(config.rutas.visitas_yaml),
            apiario=apiario,
            fecha=fecha,
            desde=desde,
            hasta=hasta,
            responsable=responsable,
            correo=correo,
            chat=chat,
            notas=notas,
            origen="cli",
            ahora=momento,
        )
    except ErrorVisitas as e:
        typer.secho(f"No se registró la visita: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e
    typer.echo(f"Visita registrada: {v.id}")
    for h in config.ajustes.hitos_horas:
        m = momento_hito(v.inicio, h)
        estado = "aprox. " + tiempo.fmt_momento(m) if m > momento else "ya vencido (se envía el más cercano al inicio)"
        typer.echo(f"  Informe {h} h: {estado}")


@app.command()
def listar(
    todas: Annotated[bool, typer.Option("--todas", help="Incluir pasadas y canceladas.")] = False,
    ahora: OpcionAhora = None,
    base: OpcionBase = None,
) -> None:
    """Lista las visitas y el estado de sus informes."""
    config = _config(base)
    momento = _ahora(ahora)
    estado = EstadoEnvios(config.rutas.envios_json)
    visitas = sorted(RepositorioYAML(config.rutas.visitas_yaml).listar(), key=lambda v: v.inicio)
    if not todas:
        visitas = [v for v in visitas if v.estado == "planificada" and v.fin > momento]
    if not visitas:
        typer.echo("No hay visitas" + ("" if todas else " planificadas a futuro") + ".")
        return
    for v in visitas:
        hitos = " · ".join(f"{h} h: {estado.hito(v.id, h).estado}" for h in config.ajustes.hitos_horas)
        typer.echo(
            f"{v.id}  {tiempo.fmt_dia_fecha(v.fecha)} {tiempo.fmt_hora(v.desde)}–{tiempo.fmt_hora(v.hasta)}"
            f"  [{v.estado}]  {v.responsable or '-'}  ({hitos})"
        )


@app.command()
def cancelar(visita_id: Annotated[str, typer.Argument(help="Id de la visita.")], base: OpcionBase = None) -> None:
    """Cancela una visita (no se envían más informes)."""
    config = _config(base)
    try:
        v = RepositorioYAML(config.rutas.visitas_yaml).cancelar(visita_id)
    except ErrorVisitas as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e
    typer.echo(f"Visita cancelada: {v.id}")


@app.command()
def informe(
    visita_id: Annotated[str, typer.Argument(help="Id de la visita.")],
    hito: Annotated[int, typer.Option(help="24 o 12 (horas antes del inicio).")] = 24,
    enviar: Annotated[bool, typer.Option("--enviar", help="Enviarlo ahora por los canales de la visita.")] = False,
    vista_previa: Annotated[Path | None, typer.Option("--vista-previa", help="Guardar el HTML sin enviar.")] = None,
    ahora: OpcionAhora = None,
    base: OpcionBase = None,
) -> None:
    """Genera el informe de una visita con datos actuales (no cambia el estado de envíos)."""
    from interfaz4.motor import Motor, informe_previo

    config = _config(base)
    momento = _ahora(ahora)
    try:
        v = RepositorioYAML(config.rutas.visitas_yaml).obtener(visita_id)
    except ErrorVisitas as e:
        typer.secho(str(e), fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e
    datos = recolectar(config, v, hito, momento, construir_recolector(config))
    render = generar(datos, informe_previo(config, v.id, hito), config.ajustes.informe.incluir_comparacion_24_12)
    if vista_previa:
        vista_previa.write_text(render.html, encoding="utf-8")
        vista_previa.with_suffix(".txt").write_text(render.texto, encoding="utf-8")
        typer.echo(f"Vista previa: {vista_previa} (y {vista_previa.with_suffix('.txt')})")
    if enviar:
        canales = [c for c in v.canales if config.ajustes.canal_habilitado(c)]
        resultado = Motor(config).enviar(v, hito, render, canales)
        for canal, est in resultado.items():
            typer.echo(f"{canal}: {est}")
        if any(e.startswith("error") for e in resultado.values()):
            raise typer.Exit(1)
    if not vista_previa and not enviar:
        typer.echo(f"Asunto: {render.asunto}\n")
        typer.echo(render.texto)


@app.command()
def ejecutar(ahora: OpcionAhora = None, base: OpcionBase = None) -> None:
    """Envía los informes con hito vencido (pensado para correr cada hora)."""
    from interfaz4.motor import Motor
    from interfaz4.publicar import exportar

    config = _config(base)
    momento = _ahora(ahora)
    try:
        resultado = Motor(config).ejecutar(momento)
    except ErrorVisitas as e:
        typer.secho(f"datos/visitas.yaml inválido: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from e
    exportar(config, momento)
    texto = resultado.resumen()
    typer.echo(texto)
    _resumen_github("### Interfaz 4 — motor\n\n" + texto)


@app.command("probar-fuentes")
def probar_fuentes(base: OpcionBase = None) -> None:
    """Chequeo de salud de cada fuente para las próximas 6 horas en cada apiario."""
    config = _config(base)
    momento = tiempo.ahora()
    recolector = construir_recolector(config)
    desde = tiempo.techo_hora(momento)
    hasta = tiempo.sumar_horas(desde, 6)
    lineas = [f"Chequeo de fuentes · {tiempo.fmt_momento(momento)} · filas {tiempo.fmt_hora(desde)}–{tiempo.fmt_hora(hasta)}"]
    falla = False
    for apiario in config.apiarios.values():
        for nombre in recolector.fuentes:
            serie = recolector.serie(nombre, apiario, desde, hasta, "todas")
            con_dato = sum(1 for p in serie.puntos if p.temp_c is not None)
            ok = con_dato > 0
            falla |= not ok
            lineas.append(
                f"- {apiario.id} · {nombre}: {'OK' if ok else 'SIN DATOS'} "
                f"({con_dato}/{len(serie.puntos)} horas con temperatura; {serie.detalle_emision or 's/d'})"
                + (f" · avisos: {'; '.join(serie.errores)}" if serie.errores else "")
            )
        alertas = recolector.alertas(apiario, desde, hasta)
        if alertas is None:
            lineas.append(f"- {apiario.id} · smn_cap: deshabilitada")
        else:
            falla |= not alertas.disponible
            lineas.append(
                f"- {apiario.id} · smn_cap: "
                + (f"OK ({len(alertas.alertas)} alertas vigentes para el punto)" if alertas.disponible else "NO DISPONIBLE")
                + (f" · {'; '.join(alertas.errores)}" if alertas.errores else "")
            )
    s = config.secretos
    lineas.append(f"- correo: {'configurado' if s.smtp_configurado else 'SIN CONFIGURAR'} ({s.smtp_host}:{s.smtp_port}, {s.smtp_seguridad}); destinatario por defecto: {'sí' if s.correo_destino_por_defecto else 'no'}")
    lineas.append(f"- google_chat: {'habilitado' if config.ajustes.canal_habilitado('google_chat') else 'deshabilitado'}; webhook {'cargado' if s.gchat_webhook_url else 'sin cargar'}")
    texto = "\n".join(lineas)
    typer.echo(texto)
    _resumen_github("### Interfaz 4 — fuentes\n\n" + texto)
    if falla:
        raise typer.Exit(1)


@app.command("procesar-issue")
def procesar_issue(
    evento: Annotated[Path, typer.Option(help="JSON del evento (GITHUB_EVENT_PATH).")],
    comentario: Annotated[Path, typer.Option(help="Dónde escribir el comentario de respuesta.")] = Path("comentario.md"),
    salida: Annotated[Path | None, typer.Option(help="JSON con el resultado (para el workflow).")] = None,
    ahora: OpcionAhora = None,
    base: OpcionBase = None,
) -> None:
    """Registra o cancela una visita a partir de un issue de GitHub."""
    from interfaz4.issues import procesar_evento

    config = _config(base)
    datos = json.loads(evento.read_text(encoding="utf-8"))
    resultado = procesar_evento(config, datos, _ahora(ahora))
    if resultado.comentario:
        comentario.write_text(resultado.comentario + "\n", encoding="utf-8")
    info = {
        "procesado": resultado.procesado,
        "accion": resultado.accion,
        "ok": resultado.ok,
        "cambios": resultado.cambios,
        "cerrar": resultado.cerrar,
        "visita_id": resultado.visita_id,
        "comentar": bool(resultado.comentario),
    }
    if salida:
        salida.write_text(json.dumps(info) + "\n", encoding="utf-8")
    salida_gh = os.environ.get("GITHUB_OUTPUT")
    if salida_gh:
        with open(salida_gh, "a", encoding="utf-8") as f:
            for k, v in info.items():
                f.write(f"{k}={str(v).lower() if isinstance(v, bool) else (v or '')}\n")
    typer.echo(json.dumps(info, ensure_ascii=False))


@app.command()
def publicar(ahora: OpcionAhora = None, base: OpcionBase = None) -> None:
    """Regenera publico/ (estado.json e informes HTML para la web)."""
    from interfaz4.publicar import exportar

    config = _config(base)
    cambio = exportar(config, _ahora(ahora))
    typer.echo("publico/ actualizado" if cambio else "publico/ sin cambios")


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(app())
