"""Fuente D — Open-Meteo Forecast API (opcional, APAGADA por defecto).

El plan gratuito es solo para uso NO comercial (open-meteo.com/en/terms).
El 03/10/2026 el usuario decidió dejarla apagada (`fuentes.open_meteo.
habilitada: false`). Queda implementada detrás del flag por si en el futuro
el uso califica como no comercial.

Convención: `precipitation`, `precipitation_probability` y `wind_gusts_10m`
en t se refieren a la hora anterior (t−1h, t] → la fila H usa t = H+1.
Atribución obligatoria: "Weather data by Open-Meteo.com" (CC BY 4.0).
"""

from __future__ import annotations

from datetime import datetime

from interfaz4 import normalizar, tiempo
from interfaz4.fuentes.base import ErrorFuente, Fuente, Reloj, Variables, reloj_real
from interfaz4.fuentes.http import ClienteHTTP
from interfaz4.modelos import Apiario, SerieFuente

URL = "https://api.open-meteo.com/v1/forecast"
VARIABLES = (
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation_probability",
    "precipitation",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
)


class FuenteOpenMeteo(Fuente):
    nombre = "open_meteo"
    etiqueta = "Open-Meteo"

    def __init__(self, http: ClienteHTTP, reloj: Reloj = reloj_real) -> None:
        super().__init__(reloj)
        self.http = http

    @staticmethod
    def parametros(apiario: Apiario, inicio: datetime, fin: datetime) -> dict[str, str]:
        lat, lon = apiario.coord_4
        return {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "hourly": ",".join(VARIABLES),
            "timezone": tiempo.ZONA_HORARIA,
            "wind_speed_unit": "kmh",
            # La última fila H necesita el valor en H+1 (= fin).
            "start_hour": tiempo.a_local(inicio).strftime("%Y-%m-%dT%H:%M"),
            "end_hour": tiempo.a_local(fin).strftime("%Y-%m-%dT%H:%M"),
        }

    def obtener(
        self, apiario: Apiario, inicio: datetime, fin: datetime, variables: Variables = "todas"
    ) -> SerieFuente:
        filas = tiempo.rango_horas(inicio, fin)
        try:
            resp = self.http.get(URL, params=self.parametros(apiario, inicio, fin))
            if resp.status_code != 200:
                raise ErrorFuente(f"Open-Meteo respondió HTTP {resp.status_code}")
            horario = resp.json()["hourly"]
            tiempos = horario["time"]
        except ErrorFuente as e:
            return self.serie_vacia(inicio, fin, str(e))
        except (KeyError, TypeError, ValueError) as e:
            return self.serie_vacia(inicio, fin, f"Open-Meteo: formato inesperado ({e})")

        def col(nombre: str) -> list:
            valores = horario.get(nombre) or []
            return valores if len(valores) == len(tiempos) else [None] * len(tiempos)

        instantaneos: dict[datetime, dict] = {}
        acumulados: dict[datetime, dict] = {}
        columnas = {v: col(v) for v in VARIABLES}
        for i, texto in enumerate(tiempos):
            t = datetime.fromisoformat(texto).replace(tzinfo=tiempo.ZONA_AR)
            instantaneos[t] = {
                "temp_c": columnas["temperature_2m"][i],
                "hr_pct": columnas["relative_humidity_2m"][i],
                "viento_kmh": columnas["wind_speed_10m"][i],
                "viento_dir_grados": columnas["wind_direction_10m"][i],
            }
            acumulados[t] = {
                "precip_mm": columnas["precipitation"][i],
                "prob_precip_pct": columnas["precipitation_probability"][i],
                "rafaga_kmh": columnas["wind_gusts_10m"][i],
            }
        return SerieFuente(
            fuente="open_meteo",
            emitido_utc=None,
            obtenido_utc=self.reloj(),
            puntos=normalizar.armar_puntos(filas, instantaneos, acumulados, normalizar.Convencion.HORA_QUE_TERMINA),
            detalle_emision="consulta en el momento del informe",
        )
