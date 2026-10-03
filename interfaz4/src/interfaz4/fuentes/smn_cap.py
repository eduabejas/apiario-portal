"""Fuente C — Alertas y avisos del SMN en formato CAP (RSS + XML).

Proceso: feed RSS → cada XML CAP → se incluyen solo las alertas cuyo
polígono (o círculo) contiene la coordenada del apiario y cuya vigencia se
superpone con la ventana de la visita. Los textos se copian textuales.

Si el feed responde 403 o un challenge anti-bot, la fuente se deshabilita en
esa ejecución y el informe dice "Alertas SMN no disponibles en esta
ejecución". No se evade ninguna protección.
"""

from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime

from defusedxml import ElementTree as ET
from shapely import make_valid
from shapely.geometry import Point, Polygon

from interfaz4 import tiempo
from interfaz4.fuentes.base import ErrorFuente, Reloj, reloj_real
from interfaz4.fuentes.http import ClienteHTTP, parece_challenge
from interfaz4.modelos import Alerta, Apiario, ResultadoAlertas

log = logging.getLogger(__name__)

FEED = "https://ssl.smn.gob.ar/CAP/AR.php"
NAMESPACES_CAP = ("urn:oasis:names:tc:emergency:cap:1.2", "urn:oasis:names:tc:emergency:cap:1.1")
RADIO_TIERRA_KM = 6371.0


@dataclass
class AlertaGeo:
    alerta: Alerta
    poligonos: list[Polygon] = field(default_factory=list)
    circulos: list[tuple[float, float, float]] = field(default_factory=list)  # lat, lon, radio_km

    @property
    def tiene_geometria(self) -> bool:
        return bool(self.poligonos or self.circulos)

    def contiene(self, lat: float, lon: float) -> bool:
        punto = Point(lon, lat)
        if any(p.covers(punto) for p in self.poligonos):
            return True
        return any(distancia_km(lat, lon, la, lo) <= r for la, lo, r in self.circulos)


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * RADIO_TIERRA_KM * math.asin(min(1.0, math.sqrt(a)))


def _fecha(texto: str | None) -> datetime | None:
    if not texto or not texto.strip():
        return None
    try:
        dt = datetime.fromisoformat(texto.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return tiempo.a_local(dt) if dt.tzinfo else dt.replace(tzinfo=tiempo.ZONA_AR)


def _texto(nodo, etiqueta: str, ns: dict[str, str]) -> str | None:
    valor = nodo.findtext(f"cap:{etiqueta}", default=None, namespaces=ns)
    return valor.strip() if valor and valor.strip() else None


def parsear_feed(contenido: bytes) -> list[str]:
    """Enlaces a los XML CAP del feed RSS, sin duplicados y en orden."""
    raiz = ET.fromstring(contenido)
    enlaces: list[str] = []
    for item in raiz.iter("item"):
        enlace = (item.findtext("link") or item.findtext("guid") or "").strip()
        if enlace.startswith("https://") and enlace not in enlaces:
            enlaces.append(enlace)
    return enlaces


def _poligono(texto: str) -> Polygon | None:
    try:
        pares = [tuple(float(v) for v in par.split(",")) for par in texto.split()]
    except ValueError:
        return None
    coords = [(lon, lat) for lat, lon in pares if -90 <= lat <= 90 and -180 <= lon <= 180]
    if len(coords) < 3:
        return None
    poligono = Polygon(coords)
    return poligono if poligono.is_valid else make_valid(poligono)


def _circulo(texto: str) -> tuple[float, float, float] | None:
    try:
        centro, radio = texto.split()
        lat, lon = (float(v) for v in centro.split(","))
        return lat, lon, float(radio)
    except ValueError:
        return None


def parsear_cap(contenido: bytes, url: str | None = None) -> list[AlertaGeo]:
    """Una AlertaGeo por bloque <info> en español (o por todos si no hay)."""
    raiz = ET.fromstring(contenido)
    ns_uri = raiz.tag[1:].split("}", 1)[0] if raiz.tag.startswith("{") else ""
    if ns_uri not in NAMESPACES_CAP or not raiz.tag.endswith("alert"):
        raise ValueError(f"no es un mensaje CAP ({raiz.tag})")
    ns = {"cap": ns_uri}
    if (_texto(raiz, "status", ns) or "Actual") != "Actual" or _texto(raiz, "msgType", ns) == "Cancel":
        return []
    identificador = _texto(raiz, "identifier", ns) or (url or "sin-identificador")
    enviada = _fecha(_texto(raiz, "sent", ns))
    infos = raiz.findall("cap:info", ns)
    en_espanol = [i for i in infos if (_texto(i, "language", ns) or "es").lower().startswith("es")]
    resultado: list[AlertaGeo] = []
    for n, info in enumerate(en_espanol or infos):
        areas, poligonos, circulos = [], [], []
        for area in info.findall("cap:area", ns):
            descripcion = _texto(area, "areaDesc", ns)
            if descripcion:
                areas.append(descripcion)
            for pol in area.findall("cap:polygon", ns):
                p = _poligono(pol.text or "")
                if p is not None:
                    poligonos.append(p)
            for circ in area.findall("cap:circle", ns):
                c = _circulo(circ.text or "")
                if c is not None:
                    circulos.append(c)
        alerta = Alerta(
            identificador=identificador if len(en_espanol or infos) == 1 else f"{identificador}#{n + 1}",
            enviada=enviada,
            evento=_texto(info, "event", ns) or "",
            severidad=_texto(info, "severity", ns),
            urgencia=_texto(info, "urgency", ns),
            certeza=_texto(info, "certainty", ns),
            inicio=_fecha(_texto(info, "onset", ns)) or _fecha(_texto(info, "effective", ns)),
            expira=_fecha(_texto(info, "expires", ns)),
            titular=_texto(info, "headline", ns),
            descripcion=_texto(info, "description", ns),
            instruccion=_texto(info, "instruction", ns),
            areas=areas,
            remitente=_texto(info, "senderName", ns),
            url=url or _texto(info, "web", ns),
        )
        resultado.append(AlertaGeo(alerta, poligonos, circulos))
    return resultado


def superpone(alerta: Alerta, inicio: datetime, fin: datetime) -> bool:
    """Vigencia [onset|effective|sent, expires] contra la ventana [inicio, fin)."""
    desde = alerta.inicio or alerta.enviada
    return (desde is None or desde < fin) and (alerta.expira is None or alerta.expira > inicio)


class FuenteAlertasSMN:
    nombre = "smn_cap"
    etiqueta = "Alertas SMN"

    def __init__(self, http: ClienteHTTP, reloj: Reloj = reloj_real, max_hilos: int = 6) -> None:
        self.http = http
        self.reloj = reloj
        self.max_hilos = max_hilos
        self._enlaces: list[str] | None = None
        self._error_feed: str | None = None
        self._alertas: dict[str, list[AlertaGeo] | str] = {}

    def _leer_feed(self) -> list[str]:
        if self._error_feed:
            raise ErrorFuente(self._error_feed)
        if self._enlaces is None:
            try:
                resp = self.http.get(FEED)
            except ErrorFuente as e:
                self._error_feed = f"Feed CAP del SMN inaccesible: {e}"
                raise ErrorFuente(self._error_feed) from e
            if parece_challenge(resp):
                self._error_feed = f"El feed CAP del SMN respondió HTTP {resp.status_code} o una verificación anti-bot: fuente deshabilitada en esta ejecución"
            elif resp.status_code != 200:
                self._error_feed = f"El feed CAP del SMN respondió HTTP {resp.status_code}"
            if self._error_feed:
                raise ErrorFuente(self._error_feed)
            try:
                self._enlaces = parsear_feed(resp.content)
            except ET.ParseError as e:
                self._error_feed = f"Feed CAP del SMN con XML inválido: {e}"
                raise ErrorFuente(self._error_feed) from e
        return self._enlaces

    def _leer_alerta(self, url: str) -> list[AlertaGeo] | str:
        try:
            resp = self.http.get(url)
            if parece_challenge(resp) or resp.status_code != 200:
                return f"HTTP {resp.status_code}"
            return parsear_cap(resp.content, url)
        except Exception as e:  # red, XML inválido, etc.
            return f"{type(e).__name__}: {e}"

    def obtener(self, apiario: Apiario, inicio: datetime, fin: datetime) -> ResultadoAlertas:
        try:
            enlaces = self._leer_feed()
        except ErrorFuente as e:
            return ResultadoAlertas(disponible=False, errores=[str(e)], obtenido_utc=self.reloj())
        pendientes = [u for u in enlaces if u not in self._alertas]
        if pendientes:
            with ThreadPoolExecutor(max_workers=self.max_hilos) as pool:
                for url, res in zip(pendientes, pool.map(self._leer_alerta, pendientes), strict=True):
                    self._alertas[url] = res
        vistas: set[str] = set()
        incluidas: list[Alerta] = []
        fallidas = 0
        sin_geometria = 0
        for url in enlaces:
            res = self._alertas[url]
            if isinstance(res, str):
                fallidas += 1
                log.warning("CAP %s: %s", url, res)
                continue
            for ag in res:
                if not ag.tiene_geometria:
                    sin_geometria += 1
                    continue
                if ag.alerta.identificador in vistas:
                    continue
                if ag.contiene(apiario.lat, apiario.lon) and superpone(ag.alerta, inicio, fin):
                    vistas.add(ag.alerta.identificador)
                    incluidas.append(ag.alerta)
        errores = []
        if fallidas:
            errores.append(f"{fallidas} de {len(enlaces)} avisos del feed no se pudieron leer")
        if sin_geometria:
            log.info("CAP: %d bloques sin polígono ni círculo (no evaluables por punto)", sin_geometria)
        incluidas.sort(key=lambda a: (a.inicio or a.enviada or fin, a.identificador))
        return ResultadoAlertas(disponible=True, alertas=incluidas, errores=errores, obtenido_utc=self.reloj())
