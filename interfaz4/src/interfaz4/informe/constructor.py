"""Arma el informe a partir de los datos recolectados.

Solo organiza: resumen por fuente (mínimos, máximos, sumas), tramo previo,
detalle horario, diferencias numéricas 24 h → 12 h, alertas textuales y pie
de fuentes y licencias. No califica, no recomienda, no promedia fuentes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from jinja2 import Environment, PackageLoader, StrictUndefined, select_autoescape

from interfaz4 import tiempo
from interfaz4.informe.recoleccion import DatosInforme
from interfaz4.modelos import Alerta, PuntoHorario, SerieFuente

SD = "s/d"
ETIQUETAS = {
    "smn_wrf": "SMN WRF",
    "metno": "MET Norway",
    "open_meteo": "Open-Meteo",
    "ecmwf_ens": "ECMWF ENS",
    "smn_cap": "Alertas SMN",
}
ATRIBUCIONES = {
    "smn_wrf": "Pronóstico WRF-SMN © Servicio Meteorológico Nacional (Argentina), CC BY 2.5 AR.",
    "metno": "Datos de MET Norway (api.met.no), CC BY 4.0.",
    "smn_cap": "Alertas: Servicio Meteorológico Nacional (CAP), CC BY 4.0.",
    "open_meteo": "Weather data by Open-Meteo.com, CC BY 4.0.",
    "ecmwf_ens": "ECMWF Open Data, CC BY 4.0.",
}
LEYENDA = (
    "Este informe presenta datos de pronóstico sin interpretación. "
    "Las decisiones quedan a criterio de quien visita el apiario."
)
COLUMNAS_DETALLE = ["Hora", "Temp", "HR", "Viento", "Dir", "Ráfaga", "Lluvia", "Prob."]
LIMITE_CHAT = 3800


# ------------------------------------------------------------------ formato


def fmt_num(v: float | None, decimales: int) -> str:
    """Número con coma decimal (es-AR); None → 's/d'."""
    if v is None:
        return SD
    texto = f"{round(v, decimales):.{decimales}f}"
    if texto.lstrip("-").strip("0,.") == "":
        texto = texto.lstrip("-")  # evita "-0,0"
    return texto.replace(".", ",")


def fmt_dif(antes: float, despues: float, decimales: int) -> str:
    d = round(round(despues, decimales) - round(antes, decimales), decimales)
    if d == 0:
        return f"±{fmt_num(0.0, decimales)}"
    return ("+" if d > 0 else "−") + fmt_num(abs(d), decimales)


def tabla_texto(encabezados: list[str], filas: list[list[str]]) -> str:
    """Tabla monoespaciada: primera columna a la izquierda, el resto a la derecha."""
    anchos = [max(len(str(f[i])) for f in [encabezados, *filas]) for i in range(len(encabezados))]

    def linea(celdas: list[str]) -> str:
        partes = [str(c).ljust(anchos[0]) if i == 0 else str(c).rjust(anchos[i]) for i, c in enumerate(celdas)]
        return "  ".join(partes).rstrip()

    return "\n".join([linea(encabezados), *(linea(f) for f in filas)])


# ------------------------------------------------------------------ resumen


@dataclass
class Resumen:
    temp_min: float | None = None
    temp_max: float | None = None
    hr_min: float | None = None
    hr_max: float | None = None
    viento_max: float | None = None
    viento_rumbo: str | None = None
    rafaga_max: float | None = None
    precip_total: float | None = None
    precip_horas: int = 0
    horas: int = 0
    prob_max: float | None = None

    @property
    def precip_completa(self) -> bool:
        return self.precip_horas == self.horas


def resumir(puntos: list[PuntoHorario]) -> Resumen:
    def disponibles(campo: str) -> list[float]:
        return [getattr(p, campo) for p in puntos if getattr(p, campo) is not None]

    r = Resumen(horas=len(puntos))
    temps, hrs = disponibles("temp_c"), disponibles("hr_pct")
    if temps:
        r.temp_min, r.temp_max = min(temps), max(temps)
    if hrs:
        r.hr_min, r.hr_max = min(hrs), max(hrs)
    con_viento = [p for p in puntos if p.viento_kmh is not None]
    if con_viento:
        mayor = max(con_viento, key=lambda p: p.viento_kmh)  # primera hora con el máximo
        r.viento_max, r.viento_rumbo = mayor.viento_kmh, mayor.viento_dir_cardinal
    rafagas, probs, lluvias = disponibles("rafaga_kmh"), disponibles("prob_precip_pct"), disponibles("precip_mm")
    r.rafaga_max = max(rafagas) if rafagas else None
    r.prob_max = max(probs) if probs else None
    r.precip_horas = len(lluvias)
    r.precip_total = sum(lluvias) if lluvias else None
    return r


def fmt_precip_total(r: Resumen, unidad: str = "") -> str:
    if r.precip_total is None:
        return SD
    texto = fmt_num(r.precip_total, 1) + unidad
    return texto if r.precip_completa else f"{texto} ({r.precip_horas} de {r.horas} h)"


def filas_resumen(resumenes: list[Resumen]) -> list[tuple[str, list[str]]]:
    def par(a: float | None, b: float | None, dec: int) -> str:
        return SD if a is None or b is None else f"{fmt_num(a, dec)} / {fmt_num(b, dec)}"

    def viento(r: Resumen) -> str:
        if r.viento_max is None:
            return SD
        return f"{fmt_num(r.viento_max, 0)} · {r.viento_rumbo}" if r.viento_rumbo else fmt_num(r.viento_max, 0)

    return [
        ("Temp. mín / máx (°C)", [par(r.temp_min, r.temp_max, 1) for r in resumenes]),
        ("Humedad mín / máx (%)", [par(r.hr_min, r.hr_max, 0) for r in resumenes]),
        ("Viento máx (km/h) · rumbo", [viento(r) for r in resumenes]),
        ("Ráfaga máx (km/h)", [fmt_num(r.rafaga_max, 0) for r in resumenes]),
        ("Precipitación total (mm)", [fmt_precip_total(r) for r in resumenes]),
        ("Prob. precipitación máx (%)", [fmt_num(r.prob_max, 0) for r in resumenes]),
    ]


CAMPOS_COMPARACION = [
    ("temp_min", "Temp. mín", "°C", 1),
    ("temp_max", "Temp. máx", "°C", 1),
    ("hr_min", "Humedad mín", "%", 0),
    ("hr_max", "Humedad máx", "%", 0),
    ("viento_max", "Viento máx", "km/h", 0),
    ("rafaga_max", "Ráfaga máx", "km/h", 0),
    ("precip_total", "Precip. total", "mm", 1),
    ("prob_max", "Prob. precip. máx", "%", 0),
]


def comparar(previo: DatosInforme, actual: DatosInforme) -> list[str]:
    """Diferencias numéricas por variable resumen y fuente (sin adjetivos)."""
    antes = {s.fuente: resumir(s.puntos) for s in previo.series}
    lineas: list[str] = []
    for serie in actual.series:
        if serie.fuente not in antes:
            continue
        r0, r1 = antes[serie.fuente], resumir(serie.puntos)
        etiqueta = ETIQUETAS.get(serie.fuente, serie.fuente)
        for campo, nombre, unidad, dec in CAMPOS_COMPARACION:
            v0, v1 = getattr(r0, campo), getattr(r1, campo)
            if v0 is None and v1 is None:
                continue
            texto = f"{nombre} {etiqueta}: {fmt_num(v0, dec)} → {fmt_num(v1, dec)} {unidad}"
            if v0 is not None and v1 is not None:
                texto += f" ({fmt_dif(v0, v1, dec)})"
            lineas.append(texto)
    return lineas


# --------------------------------------------------------------------- vista


@dataclass
class VistaAlerta:
    titular: str
    evento: str
    clasificacion: str
    vigencia: str
    areas: str
    descripcion: str | None
    instruccion: str | None
    url: str | None


@dataclass
class VistaDetalle:
    titulo: str
    filas: list[list[str]]
    errores: list[str]


@dataclass
class VistaInforme:
    asunto: str
    titulo: str
    apiario_linea: str
    visita_linea: str
    responsable_linea: str
    generado_linea: str
    alertas_estado: str  # "con" | "sin" | "no_disponible" | "deshabilitada"
    alertas_mensaje: str
    alertas: list[VistaAlerta]
    columnas: list[str]
    resumen: list[tuple[str, list[str]]]
    notas_resumen: list[str]
    tramo_titulo: str | None
    tramo_partes: list[str]
    detalles: list[VistaDetalle]
    cambios_titulo: str | None
    cambios: list[str]
    pie_fuentes: list[str]
    atribuciones: list[str]
    leyenda: str = LEYENDA
    avisos: list[str] = field(default_factory=list)

    @property
    def resumen_texto(self) -> str:
        return tabla_texto(["", *self.columnas], [[etq, *vals] for etq, vals in self.resumen])

    def detalle_texto(self, d: VistaDetalle) -> str:
        return tabla_texto(COLUMNAS_DETALLE, d.filas)


def _fila_detalle(p: PuntoHorario) -> list[str]:
    return [
        tiempo.fmt_hora(p.hora_local),
        fmt_num(p.temp_c, 1),
        fmt_num(p.hr_pct, 0),
        fmt_num(p.viento_kmh, 0),
        p.viento_dir_cardinal or SD,
        fmt_num(p.rafaga_kmh, 0),
        fmt_num(p.precip_mm, 1),
        fmt_num(p.prob_precip_pct, 0),
    ]


def _emision(serie: SerieFuente) -> str:
    return serie.detalle_emision or (
        f"emitido {tiempo.fmt_utc_ciclo(serie.emitido_utc)}" if serie.emitido_utc else "emisión s/d"
    )


def _vista_alerta(a: Alerta) -> VistaAlerta:
    desde = a.inicio or a.enviada
    vigencia = f"desde {tiempo.fmt_momento(desde) if desde else SD} hasta {tiempo.fmt_momento(a.expira) if a.expira else SD}"
    clasif = " · ".join(
        f"{n}: {v}" for n, v in (("Severidad", a.severidad), ("Urgencia", a.urgencia), ("Certeza", a.certeza)) if v
    )
    return VistaAlerta(
        titular=a.titular or a.evento,
        evento=a.evento,
        clasificacion=clasif,
        vigencia=vigencia,
        areas=" / ".join(a.areas),
        descripcion=a.descripcion,
        instruccion=a.instruccion,
        url=a.url,
    )


def construir_vista(datos: DatosInforme, previo: DatosInforme | None = None, comparar_24_12: bool = True) -> VistaInforme:
    v, a = datos.visita, datos.apiario
    lat4, lon4 = a.coord_4
    generado = tiempo.a_local(datos.generado)
    proximo = (
        f"Próximo informe: ~{tiempo.fmt_hora_dia(datos.proximo_informe)}"
        if datos.proximo_informe
        else "Último informe programado para esta visita"
    )
    responsable = f"Responsable: {v.responsable or SD}"
    if v.notas:
        responsable += f" · Notas: {v.notas}"

    # Alertas
    if datos.alertas is None:
        estado, mensaje = "deshabilitada", "Alertas SMN: fuente deshabilitada en la configuración."
    elif not datos.alertas.disponible:
        estado, mensaje = "no_disponible", "Alertas SMN no disponibles en esta ejecución."
    elif not datos.alertas.alertas:
        estado, mensaje = "sin", "Sin alertas SMN vigentes para este punto y horario."
    else:
        n = len(datos.alertas.alertas)
        estado, mensaje = "con", f"{n} alerta{'s' if n > 1 else ''} SMN vigente{'s' if n > 1 else ''} para este punto y horario (texto copiado del SMN):"
    alertas = [_vista_alerta(x) for x in datos.alertas.alertas] if datos.alertas and datos.alertas.disponible else []

    # Resumen
    columnas = [ETIQUETAS.get(s.fuente, s.fuente) for s in datos.series]
    resumenes = [resumir(s.puntos) for s in datos.series]
    notas_resumen = ["s/d = sin dato en la fuente."]
    if resumenes and all(r.rafaga_max is None and r.prob_max is None for r in resumenes):
        notas_resumen.append(
            "Ráfagas y probabilidad de precipitación: "
            + " y ".join(columnas)
            + (" no publican esos datos" if len(columnas) > 1 else " no publica esos datos")
            + " para este punto."
        )

    # Tramo previo
    tramo_titulo, tramo_partes = None, []
    if datos.tramo_desde and datos.tramo_hasta:
        tramo_titulo = (
            f"ANTES DE LA VISITA ({tiempo.fmt_hora_dia(datos.tramo_desde)} → {tiempo.fmt_hora_dia(datos.tramo_hasta)})"
        )
        for s in datos.series_previas:
            tramo_partes.append(f"{ETIQUETAS.get(s.fuente, s.fuente)} {fmt_precip_total(resumir(s.puntos), ' mm')}")

    # Detalle horario
    detalles = [
        VistaDetalle(
            titulo=f"DETALLE HORARIO — {ETIQUETAS.get(s.fuente, s.fuente)} ({_emision(s)})",
            filas=[_fila_detalle(p) for p in s.puntos],
            errores=list(s.errores),
        )
        for s in datos.series
    ]

    # Cambios 24 → 12
    cambios_titulo, cambios = None, []
    if comparar_24_12 and previo is not None:
        cambios_titulo = (
            f"CAMBIOS RESPECTO AL INFORME DE {previo.hito} H "
            f"(generado {tiempo.fmt_momento(previo.generado)})"
        )
        cambios = comparar(previo, datos) or ["Sin valores comparables entre ambos informes."]

    # Pie
    pie = []
    for s in datos.series:
        pie.append(
            f"{ETIQUETAS.get(s.fuente, s.fuente)}: {_emision(s)} · consultado {tiempo.fmt_momento(s.obtenido_utc)}"
        )
    if datos.alertas is not None:
        if datos.alertas.disponible and datos.alertas.obtenido_utc:
            pie.append(f"Alertas SMN: consultadas {tiempo.fmt_momento(datos.alertas.obtenido_utc)}")
        elif not datos.alertas.disponible:
            pie.append("Alertas SMN: no disponibles en esta ejecución")
    usadas = [s.fuente for s in datos.series] + (["smn_cap"] if datos.alertas is not None else [])
    atribuciones = [ATRIBUCIONES[n] for n in ("smn_wrf", "metno", "smn_cap", "open_meteo", "ecmwf_ens") if n in usadas]
    avisos = []
    for s in [*datos.series, *datos.series_previas]:
        avisos.extend(f"{ETIQUETAS.get(s.fuente, s.fuente)}: {e}" for e in s.errores)
    if datos.alertas is not None:
        avisos.extend(f"Alertas SMN: {e}" for e in datos.alertas.errores)
    avisos = list(dict.fromkeys(avisos))

    return VistaInforme(
        asunto=(
            f"🐝 Visita {a.nombre} {tiempo.fmt_dd_mm(v.fecha)} {tiempo.fmt_hora(v.desde)}–{tiempo.fmt_hora(v.hasta)}"
            f" · informe {datos.hito} h"
        ),
        titulo=f"Informe de visita — {datos.hito} h antes",
        apiario_linea=f"{a.nombre} · {a.localidad} ({fmt_coord(lat4)}, {fmt_coord(lon4)})"
        if a.localidad
        else f"{a.nombre} ({fmt_coord(lat4)}, {fmt_coord(lon4)})",
        visita_linea=(
            f"Visita: {tiempo.fmt_dia_fecha(v.fecha)} · {tiempo.fmt_hora(v.desde)}–{tiempo.fmt_hora(v.hasta)} (hora Argentina)"
        ),
        responsable_linea=responsable,
        generado_linea=f"Generado: {tiempo.fmt_momento(generado)} · {proximo}",
        alertas_estado=estado,
        alertas_mensaje=mensaje,
        alertas=alertas,
        columnas=columnas,
        resumen=filas_resumen(resumenes),
        notas_resumen=notas_resumen,
        tramo_titulo=tramo_titulo,
        tramo_partes=tramo_partes,
        detalles=detalles,
        cambios_titulo=cambios_titulo,
        cambios=cambios,
        pie_fuentes=pie,
        atribuciones=atribuciones,
        avisos=avisos,
    )


def fmt_coord(v: float) -> str:
    return f"{v:.4f}"


# ----------------------------------------------------------------- render


@dataclass
class InformeRenderizado:
    asunto: str
    html: str
    texto: str
    chat: list[str]


def _entorno() -> Environment:
    return Environment(
        loader=PackageLoader("interfaz4", "informe/plantillas"),
        autoescape=select_autoescape(enabled_extensions=("html.j2",), default_for_string=False, default=False),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def dividir_mensaje(texto: str, limite: int = LIMITE_CHAT) -> list[str]:
    """Divide por secciones (líneas en blanco) sin cortar bloques ``` a la mitad."""
    bloques: list[str] = []
    actual: list[str] = []
    en_codigo = False
    for linea in texto.splitlines():
        if linea.strip().startswith("```"):
            en_codigo = not en_codigo
        actual.append(linea)
        if not en_codigo and linea.strip() == "":
            bloques.append("\n".join(actual))
            actual = []
    if actual:
        bloques.append("\n".join(actual))
    mensajes: list[str] = []
    buffer = ""
    for bloque in bloques:
        candidato = f"{buffer}\n{bloque}" if buffer else bloque
        if len(candidato) <= limite:
            buffer = candidato
            continue
        if buffer:
            mensajes.append(buffer.strip("\n"))
        while len(bloque) > limite:  # bloque gigante: corte duro por líneas
            corte = bloque.rfind("\n", 0, limite)
            corte = corte if corte > 0 else limite
            mensajes.append(bloque[:corte].strip("\n"))
            bloque = bloque[corte:]
        buffer = bloque
    if buffer.strip():
        mensajes.append(buffer.strip("\n"))
    return mensajes


def renderizar(vista: VistaInforme) -> InformeRenderizado:
    env = _entorno()
    contexto = {"v": vista, "SD": SD, "columnas_detalle": COLUMNAS_DETALLE}
    html = env.get_template("correo.html.j2").render(**contexto)
    texto = env.get_template("correo.txt.j2").render(**contexto)
    chat = env.get_template("chat.txt.j2").render(**contexto)
    return InformeRenderizado(asunto=vista.asunto, html=html, texto=texto, chat=dividir_mensaje(chat))


def generar(datos: DatosInforme, previo: DatosInforme | None = None, comparar_24_12: bool = True) -> InformeRenderizado:
    return renderizar(construir_vista(datos, previo, comparar_24_12))


def momento_iso(dt: datetime) -> str:
    return tiempo.a_local(dt).isoformat(timespec="minutes")
