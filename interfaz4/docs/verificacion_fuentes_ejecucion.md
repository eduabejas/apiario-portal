# Verificación de fuentes — ejecución automática

Generado el 2026-10-07 13:37 UTC en **GitHub Actions** (Linux 6.17.0-1022-azure, Python 3.12.14). Coordenada: -34.889180362505506, -57.82789829443907.

## A — SMN WRF-SMN determinístico (s3://smn-ar-wrf)

Consulta hecha a las 2026-10-07 13:37 UTC.

| Ciclo (UTC) | Archivos 01H | Plazos | Primera subida | Última subida | Demora (h) | Tipos |
|---|---|---|---|---|---|---|
| 2026-10-07 12 | 0 | — | — | — | — | — |
| 2026-10-07 06 | 73 | 0–72 | 08:24 | 08:39 | 2.7 | 01H, 10M, 24H |
| 2026-10-07 00 | 73 | 0–72 | 02:24 | 02:43 | 2.7 | 01H, 10M, 24H |
| 2026-10-06 18 | 73 | 0–72 | 20:22 | 20:37 | 2.6 | 01H, 10M, 24H |
| 2026-10-06 12 | 73 | 0–72 | 14:27 | 15:02 | 3.0 | 01H, 10M, 24H |
| 2026-10-06 06 | 73 | 0–72 | 08:16 | 08:32 | 2.5 | 01H, 10M, 24H |
| 2026-10-06 00 | 73 | 0–72 | 02:26 | 05:49 | 5.8 | 01H, 10M, 24H |

Ciclo completo más reciente: **2026-10-07 06 UTC**.

Archivo de muestra: `smn-ar-wrf/DATA/WRF/DET/2026/10/07/06/WRFDETAR_01H_20261007_06_012.nc` (37.4 MB).

- Dimensiones: `{'time': 1, 'y': 1249, 'x': 999}`; coordenadas: `['time', 'x', 'y', 'lat', 'lon']`
- Tiempo válido del archivo: `2026-10-07T18:00:00` (init + 12 h)
- Atributos globales: initial_condition=`SAP.SMN-ANA - 2026-10-07 06:00:00`, START_DATE=`2026-10-07 06:00:00`

| Variable | Unidad | long_name | Chunks | Compresión |
|---|---|---|---|---|
| `T2` | degree_Celsius | Calibrated 2-m Temperature | (1, 1249, 999) | zlib=True shuffle=True |
| `HR2` | percent | 2-m Relative Humidity | (1, 1249, 999) | zlib=True shuffle=True |
| `magViento10` | meter / second | Calibrated Wind Speed at 10m | (1, 1249, 999) | zlib=True shuffle=True |
| `dirViento10` | degree | Wind Direction at 10m | (1, 1249, 999) | zlib=True shuffle=True |
| `PP` | millimeter | Accumulated Total Precipitation | (1, 1249, 999) | zlib=True shuffle=True |

Otras variables del archivo: `ACLWDNB`, `ACLWUPB`, `ACSWDNB`, `Freezing_level`, `Lambert_Conformal`, `PSFC`, `SMOIS`, `TSLB`

Punto de grilla más cercano: **(iy=621, ix=662)**, lat=-34.89776, lon=-57.84357, distancia **1.72 km**. Lectura de metadatos + lat/lon 2D: 2.84 MB en 10.3 s.

Bytes descargados al leer **un solo punto** (`isel(y=iy, x=ix)`):

| Archivo | Variables | MB leídos | Segundos | Valores en el punto |
|---|---|---|---|---|
| 012 | 5 | 17.8 | 10.6 | `{'T2': 20.78, 'HR2': 62.48, 'magViento10': 6.29, 'dirViento10': 84.23, 'PP': 0.0}` |
| 013 | 1 | 4.5 | 10.9 | `{'PP': 0.13}` |

Semántica de `PP` (¿horaria o acumulada desde el inicio?) con campos completos:

- Puntos con PP(011) > 0,5 mm donde PP(012) es menor: **22134** → PP no es acumulada desde el inicio (es por intervalo).
- Archivos 10M: tiempos de `_011` = [np.float64(11.0), np.float64(11.167), np.float64(11.333), np.float64(11.5), np.float64(11.667), np.float64(11.833)] h desde init.
- Contraste con PP 10 min sobre 22729 puntos con lluvia: suma de (t−1h, t] → error medio 3.19e-08 mm; suma de [t−1h, t) → 8.45e-01 mm.
  → El `PP` del archivo válido en `t` es la lluvia del intervalo **(t−1h, t]** (hora que termina).

## B — MET Norway Locationforecast 2.0 (compact)

User-Agent usado: `interfaz4-apiarios/0.1 (+https://github.com/eduabejas/apiario-portal)` · parámetros: `{'lat': '-34.8892', 'lon': '-57.8279'}`

- HTTP **200** en 0.6 s, 40509 bytes (descomprimidos).
- Cabeceras: `{'content-type': 'application/json', 'content-encoding': 'gzip', 'expires': 'Wed, 07 Oct 2026 14:09:14 GMT', 'last-modified': 'Wed, 07 Oct 2026 13:38:07 GMT', 'age': '0', 'date': 'Wed, 07 Oct 2026 13:38:07 GMT', 'server': 'nginx/1.18.0 (Ubuntu)'}`
- `meta.updated_at`: `2026-10-07T13:17:03Z` · unidades: `{'air_pressure_at_sea_level': 'hPa', 'air_temperature': 'celsius', 'cloud_area_fraction': '%', 'precipitation_amount': 'mm', 'relative_humidity': '%', 'wind_from_direction': 'degrees', 'wind_speed': 'm/s'}`
- `geometry.coordinates`: `[-57.8279, -34.8892, 4]`
- Pasos en `timeseries`: 93 (desde `2026-10-07T13:00:00Z` hasta `2026-10-17T00:00:00Z`)
- Pasos con `next_1_hours`: 65 (último: `2026-10-10T05:00:00Z`)
- Primer paso que deja de ser horario: `2026-10-10T06:00:00Z`
- Claves `instant.details`: `['air_pressure_at_sea_level', 'air_temperature', 'cloud_area_fraction', 'relative_humidity', 'wind_from_direction', 'wind_speed']`
- Claves `next_1_hours.details`: `['precipitation_amount']`
- ¿Aparece `probability_of_precipitation`? **no**
- ¿Aparece `wind_speed_of_gust`? **no**

Ejemplo concreto (convención de intervalos):

```json
[
 {
  "time": "2026-10-07T13:00:00Z",
  "instant": {
   "air_pressure_at_sea_level": 1012.7,
   "air_temperature": 15.9,
   "cloud_area_fraction": 100.0,
   "relative_humidity": 91.2,
   "wind_from_direction": 91.4,
   "wind_speed": 8.3
  },
  "next_1_hours": {
   "summary": {
    "symbol_code": "cloudy"
   },
   "details": {
    "precipitation_amount": 0.0
   }
  }
 },
 {
  "time": "2026-10-07T14:00:00Z",
  "instant": {
   "air_pressure_at_sea_level": 1012.2,
   "air_temperature": 17.3,
   "cloud_area_fraction": 100.0,
   "relative_humidity": 85.1,
   "wind_from_direction": 89.6,
   "wind_speed": 7.8
  },
  "next_1_hours": {
   "summary": {
    "symbol_code": "heavyrain"
   },
   "details": {
    "precipitation_amount": 1.6
   }
  }
 }
]
```
→ `next_1_hours.precipitation_amount` en `time=t` es la lluvia de **[t, t+1h)** (hora que empieza).

- Repetición con `If-Modified-Since: Wed, 07 Oct 2026 13:38:07 GMT` → HTTP **304** (0 bytes, 0.4 s), Expires=`Wed, 07 Oct 2026 14:09:14 GMT`

## C — Alertas SMN (CAP)

- Feed `https://ssl.smn.gob.ar/CAP/AR.php` → HTTP **200** en 1.0 s, 118360 bytes, url final `https://ssl.smn.gob.ar/CAP/AR.php`
- Cabeceras: `{'content-type': 'application/rss+xml; charset=UTF-8', 'server': 'cloudflare', 'cf-ray': 'a46d4df04dd50ef9-ORD', 'date': 'Wed, 07 Oct 2026 13:38:08 GMT', 'last-modified': None}`
- Raíz: `rss`
- Ítems en el feed: **166**
- Estructura del primer ítem:
```text
title: TORMENTAS FUERTES CON LLUVIAS INTENSAS Y OCASIONAL CAIDA DE GRANIZO
link: https://ssl.smn.gob.ar/feeds/CAP/avisocortoplazo/2026_10_07_1309_cap_es.xml
description: Afectando parcialmente los siguientes Partidos y Departamentos: CORDOBA: Gral Roca - Pres Roque S. Pena - Rio Cuarto.
guid: https://ssl.smn.gob.ar/feeds/CAP/avisocortoplazo/2026_10_07_1309_cap_es.xml
pubDate: 
```
- Ítems por tipo: `{'avisocortoplazo': 3, 'xml_generados': 163}`
- CAP 1 (0.8 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.07.13.09.00` sent=`2026-10-07T13:09:00-03:00` infos=1 campos=`{'event': 'TORMENTAS FUERTES', 'severity': 'Severe', 'urgency': 'Immediate', 'certainty': 'Observed', 'onset': '', 'effective': '', 'expires': '2026-10-07T15:09:00-03:00', 'headline': 'AVISO NARANJA POR TORMENTAS FUERTES CON LLUVIAS INTENSAS Y OCASIONAL CAIDA DE GRANIZO', 'senderName': 'SERVICIO METEOROLOGICO NACIONAL - ARGENTINA'}` áreas=`['CORDOBA: GRAL ROCA - PRES ROQUE S.  PENA - RIO CUARTO.  (1 polígonos)']` **contiene el apiario: no**
- CAP 2 (0.8 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.07.13.13.00` sent=`2026-10-07T13:13:00-03:00` infos=1 campos=`{'event': 'TORMENTAS FUERTES', 'severity': 'Severe', 'urgency': 'Immediate', 'certainty': 'Observed', 'onset': '', 'effective': '', 'expires': '2026-10-07T15:13:00-03:00', 'headline': 'AVISO NARANJA POR TORMENTAS FUERTES CON LLUVIAS INTENSAS Y OCASIONAL CAIDA DE GRANIZO', 'senderName': 'SERVICIO METEOROLOGICO NACIONAL - ARGENTINA'}` áreas=`['CORDOBA: RIO CUARTO. SAN LUIS: CHACABUCO - GRAL PEDERNERA.  (1 polígonos)']` **contiene el apiario: no**
- CAP 3 (0.8 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.07.12.28.00` sent=`2026-10-07T12:28:00-03:00` infos=1 campos=`{'event': 'TORMENTAS FUERTES', 'severity': 'Severe', 'urgency': 'Immediate', 'certainty': 'Observed', 'onset': '', 'effective': '', 'expires': '2026-10-07T14:28:00-03:00', 'headline': 'AVISO NARANJA POR TORMENTAS FUERTES CON LLUVIAS INTENSAS Y OCASIONAL CAIDA DE GRANIZO', 'senderName': 'SERVICIO METEOROLOGICO NACIONAL - ARGENTINA'}` áreas=`['SANTA FE: BELGRANO - CASEROS - CONSTITUCION - IRIONDO - ROSA (1 polígonos)']` **contiene el apiario: no**
- CAP 4 (0.3 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.07.12.38.05.2` sent=`2026-10-07T12:38:05-03:00` infos=1 campos=`{'event': 'Lluvias', 'severity': 'Severe', 'urgency': 'Immediate', 'certainty': 'Likely', 'onset': '2026-10-07T12:38:05-03:00', 'effective': '', 'expires': '2026-10-07T14:59:59-03:00', 'headline': 'Lluvias', 'senderName': 'Servicio Meteorologico Nacional'}` áreas=`[' (1 polígonos)']` **contiene el apiario: no**
- CAP 5 (0.3 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.07.12.38.05.3` sent=`2026-10-07T12:38:05-03:00` infos=1 campos=`{'event': 'Lluvias', 'severity': 'Moderate', 'urgency': 'Future', 'certainty': 'Likely', 'onset': '2026-10-07T15:00:00-03:00', 'effective': '', 'expires': '2026-10-08T02:59:59-03:00', 'headline': 'Lluvias', 'senderName': 'Servicio Meteorologico Nacional'}` áreas=`[' (1 polígonos)']` **contiene el apiario: no**
- CAP 6 (0.8 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.07.12.38.05.5` sent=`2026-10-07T12:38:05-03:00` infos=1 campos=`{'event': 'Lluvias', 'severity': 'Moderate', 'urgency': 'Future', 'certainty': 'Likely', 'onset': '2026-10-07T15:00:00-03:00', 'effective': '', 'expires': '2026-10-08T02:59:59-03:00', 'headline': 'Lluvias', 'senderName': 'Servicio Meteorologico Nacional'}` áreas=`[' (1 polígonos)']` **contiene el apiario: no**
- CAP 7 (0.3 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.07.12.38.05.1` sent=`2026-10-07T12:38:05-03:00` infos=1 campos=`{'event': 'Lluvias', 'severity': 'Severe', 'urgency': 'Immediate', 'certainty': 'Likely', 'onset': '2026-10-07T12:38:05-03:00', 'effective': '', 'expires': '2026-10-07T14:59:59-03:00', 'headline': 'Lluvias', 'senderName': 'Servicio Meteorologico Nacional'}` áreas=`[' (1 polígonos)']` **contiene el apiario: no**
- CAP 8 (0.3 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.07.12.38.05.4` sent=`2026-10-07T12:38:05-03:00` infos=1 campos=`{'event': 'Lluvias', 'severity': 'Moderate', 'urgency': 'Future', 'certainty': 'Likely', 'onset': '2026-10-07T15:00:00-03:00', 'effective': '', 'expires': '2026-10-08T02:59:59-03:00', 'headline': 'Lluvias', 'senderName': 'Servicio Meteorologico Nacional'}` áreas=`[' (1 polígonos)']` **contiene el apiario: no**
- CAP 9 (0.3 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.07.12.38.03.106` sent=`2026-10-07T12:38:03-03:00` infos=1 campos=`{'event': 'Tormentas', 'severity': 'Moderate', 'urgency': 'Future', 'certainty': 'Likely', 'onset': '2026-10-07T15:00:00-03:00', 'effective': '', 'expires': '2026-10-08T02:59:59-03:00', 'headline': 'Tormentas', 'senderName': 'Servicio Meteorologico Nacional'}` áreas=`[' (1 polígonos)']` **contiene el apiario: no**

## D — Open-Meteo

No consultada: el usuario indicó dejarla **apagada** (uso que no califica como no comercial). Sin datos de verificación.

## Resumen

- `smn_wrf`: ok
- `metno`: ok
- `smn_cap`: ok
