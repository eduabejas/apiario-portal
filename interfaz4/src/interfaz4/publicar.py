"""Exporta el estado para la web (Interfaz 4 en GitHub Pages).

Genera `publico/estado.json` y `publico/informes/<visita>_<hito>.html`.
El repositorio es público: no se exportan correos. Los archivos se
reescriben solo si cambian, para no generar commits vacíos.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from interfaz4 import tiempo
from interfaz4.config import FUENTES_CONOCIDAS, Config
from interfaz4.estado import EstadoEnvios, momento_hito
from interfaz4.informe.constructor import ETIQUETAS
from interfaz4.modelos import CANALES
from interfaz4.motor import cargar_snapshot, renderizar_snapshot, ruta_snapshot
from interfaz4.visitas.archivo_yaml import RepositorioYAML

VERSION = 1
DIAS_HISTORIAL = 60


def escribir_si_cambia(ruta: Path, contenido: str) -> bool:
    if ruta.exists() and ruta.read_text(encoding="utf-8") == contenido:
        return False
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")
    return True


def _iso(dt: datetime | None) -> str | None:
    return tiempo.a_local(dt).isoformat(timespec="minutes") if dt else None


def _canal(estado: str) -> str:
    return "error" if estado.startswith("error") else estado


def exportar(config: Config, ahora: datetime) -> bool:
    """Devuelve True si cambió algún archivo de publico/."""
    salida = config.rutas.publico_dir
    informes = salida / "informes"
    visitas = RepositorioYAML(config.rutas.visitas_yaml).listar()
    estado = EstadoEnvios(config.rutas.envios_json)
    limite = tiempo.a_local(ahora) - timedelta(days=DIAS_HISTORIAL)
    cambios = False
    referenciados: set[str] = set()
    lista = []
    for v in sorted(visitas, key=lambda x: (x.inicio, x.id)):
        if v.fin < limite:
            continue
        hitos = []
        for h in config.ajustes.hitos_horas:
            r = estado.hito(v.id, h)
            informe = None
            datos = cargar_snapshot(ruta_snapshot(config, v.id, h))
            if datos is not None:
                nombre = f"{v.id}_{h}.html"
                cambios |= escribir_si_cambia(informes / nombre, renderizar_snapshot(config, datos).html)
                referenciados.add(nombre)
                informe = f"informes/{nombre}"
            errores = {c: e.split(":", 1)[1].strip()[:200] for c, e in r.canales.items() if e.startswith("error")}
            hitos.append(
                {
                    "horas": h,
                    "programado": _iso(momento_hito(v.inicio, h)),
                    "estado": r.estado,
                    "momento": _iso(r.momento),
                    "canales": {c: _canal(e) for c, e in sorted(r.canales.items())},
                    "errores": errores or None,
                    "detalle": r.detalle,
                    "informe": informe,
                }
            )
        lista.append(
            {
                "id": v.id,
                "apiario": v.apiario,
                "fecha": v.fecha.isoformat(),
                "desde": tiempo.fmt_hora(v.desde),
                "hasta": tiempo.fmt_hora(v.hasta),
                "inicio": _iso(v.inicio),
                "fin": _iso(v.fin),
                "responsable": v.responsable,
                "notas": v.notas,
                "estado": v.estado,
                "origen": v.origen,
                "canales": list(v.canales),
                "hitos": hitos,
            }
        )
    if informes.exists():
        for archivo in informes.glob("*.html"):
            if archivo.name not in referenciados:
                archivo.unlink()
                cambios = True
    doc = {
        "version": VERSION,
        "zona_horaria": config.zona_horaria,
        "hitos_horas": config.ajustes.hitos_horas,
        "apiarios": {
            a.id: {"nombre": a.nombre, "localidad": a.localidad, "lat": a.coord_4[0], "lon": a.coord_4[1]}
            for a in config.apiarios.values()
        },
        "fuentes": {
            n: {"nombre": ETIQUETAS.get(n, n), "habilitada": config.ajustes.fuente_habilitada(n)} for n in FUENTES_CONOCIDAS
        },
        "canales": {c: config.ajustes.canal_habilitado(c) for c in CANALES},
        "visitas": lista,
    }
    cambios |= escribir_si_cambia(salida / "estado.json", json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    return cambios
