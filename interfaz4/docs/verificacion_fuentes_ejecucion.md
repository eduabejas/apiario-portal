# Verificación de fuentes — ejecución automática

Generado el 2026-10-03 21:31 UTC en **GitHub Actions** (Linux 6.17.0-1022-azure, Python 3.12.14). Coordenada: -34.889180362505506, -57.82789829443907.

## A — SMN WRF-SMN determinístico (s3://smn-ar-wrf)

Consulta hecha a las 2026-10-03 21:31 UTC.

| Ciclo (UTC) | Archivos 01H | Plazos | Primera subida | Última subida | Demora (h) | Tipos |
|---|---|---|---|---|---|---|
| 2026-10-03 18 | 73 | 0–72 | 20:25 | 20:41 | 2.7 | 01H, 10M, 24H |
| 2026-10-03 12 | 73 | 0–72 | 14:23 | 14:42 | 2.7 | 01H, 10M, 24H |
| 2026-10-03 06 | 73 | 0–72 | 07:48 | 08:02 | 2.0 | 01H, 10M, 24H |
| 2026-10-03 00 | 73 | 0–72 | 02:21 | 02:36 | 2.6 | 01H, 10M, 24H |
| 2026-10-02 18 | 73 | 0–72 | 20:24 | 20:39 | 2.7 | 01H, 10M, 24H |
| 2026-10-02 12 | 73 | 0–72 | 14:18 | 14:35 | 2.6 | 01H, 10M, 24H |
| 2026-10-02 06 | 73 | 0–72 | 08:28 | 08:42 | 2.7 | 01H, 10M, 24H |
| 2026-10-02 00 | 73 | 0–72 | 02:21 | 02:37 | 2.6 | 01H, 10M, 24H |

Ciclo completo más reciente: **2026-10-03 18 UTC**.

Archivo de muestra: `smn-ar-wrf/DATA/WRF/DET/2026/10/03/18/WRFDETAR_01H_20261003_18_012.nc` (37.6 MB).

- Dimensiones: `{'time': 1, 'y': 1249, 'x': 999}`; coordenadas: `['time', 'x', 'y', 'lat', 'lon']`
- Tiempo válido del archivo: `2026-10-04T06:00:00` (init + 12 h)
- Atributos globales: initial_condition=`SAP.SMN-ANA - 2026-10-03 18:00:00`, START_DATE=`2026-10-03 18:00:00`

| Variable | Unidad | long_name | Chunks | Compresión |
|---|---|---|---|---|
| `T2` | degree_Celsius | Calibrated 2-m Temperature | (1, 1249, 999) | zlib=True shuffle=True |
| `HR2` | percent | 2-m Relative Humidity | (1, 1249, 999) | zlib=True shuffle=True |
| `magViento10` | meter / second | Calibrated Wind Speed at 10m | (1, 1249, 999) | zlib=True shuffle=True |
| `dirViento10` | degree | Wind Direction at 10m | (1, 1249, 999) | zlib=True shuffle=True |
| `PP` | millimeter | Accumulated Total Precipitation | (1, 1249, 999) | zlib=True shuffle=True |

Otras variables del archivo: `ACLWDNB`, `ACLWUPB`, `ACSWDNB`, `Freezing_level`, `Lambert_Conformal`, `PSFC`, `SMOIS`, `TSLB`

Punto de grilla más cercano: **(iy=621, ix=662)**, lat=-34.89776, lon=-57.84357, distancia **1.72 km**. Lectura de metadatos + lat/lon 2D: 2.84 MB en 8.5 s.

Bytes descargados al leer **un solo punto** (`isel(y=iy, x=ix)`):

| Archivo | Variables | MB leídos | Segundos | Valores en el punto |
|---|---|---|---|---|
| 012 | 5 | 18.0 | 8.8 | `{'T2': 10.63, 'HR2': 100.41, 'magViento10': 0.0, 'dirViento10': 256.9, 'PP': 0.02}` |
| 013 | 1 | 4.8 | 8.2 | `{'PP': 0.03}` |

Semántica de `PP` (¿horaria o acumulada desde el inicio?) con campos completos:

- Puntos con PP(011) > 0,5 mm donde PP(012) es menor: **43375** → PP no es acumulada desde el inicio (es por intervalo).
- Archivos 10M: tiempos de `_011` = [np.float64(11.0), np.float64(11.167), np.float64(11.333), np.float64(11.5), np.float64(11.667), np.float64(11.833)] h desde init.
- Contraste con PP 10 min sobre 41417 puntos con lluvia: suma de (t−1h, t] → error medio 2.81e-08 mm; suma de [t−1h, t) → 9.36e-01 mm.
  → El `PP` del archivo válido en `t` es la lluvia del intervalo **(t−1h, t]** (hora que termina).

## B — MET Norway Locationforecast 2.0 (compact)

User-Agent usado: `interfaz4-apiarios/0.1 (+https://github.com/eduabejas/apiario-portal)` · parámetros: `{'lat': '-34.8892', 'lon': '-57.8279'}`

- HTTP **200** en 1.0 s, 39765 bytes (descomprimidos).
- Cabeceras: `{'content-type': 'application/json', 'content-encoding': 'gzip', 'expires': 'Sat, 03 Oct 2026 22:04:15 GMT', 'last-modified': 'Sat, 03 Oct 2026 21:32:22 GMT', 'age': '0', 'date': 'Sat, 03 Oct 2026 21:32:22 GMT', 'server': 'nginx/1.18.0 (Ubuntu)'}`
- `meta.updated_at`: `2026-10-03T19:21:14Z` · unidades: `{'air_pressure_at_sea_level': 'hPa', 'air_temperature': 'celsius', 'cloud_area_fraction': '%', 'precipitation_amount': 'mm', 'relative_humidity': '%', 'wind_from_direction': 'degrees', 'wind_speed': 'm/s'}`
- `geometry.coordinates`: `[-57.8279, -34.8892, 4]`
- Pasos en `timeseries`: 90 (desde `2026-10-03T21:00:00Z` hasta `2026-10-13T00:00:00Z`)
- Pasos con `next_1_hours`: 63 (último: `2026-10-06T11:00:00Z`)
- Primer paso que deja de ser horario: `2026-10-06T12:00:00Z`
- Claves `instant.details`: `['air_pressure_at_sea_level', 'air_temperature', 'cloud_area_fraction', 'relative_humidity', 'wind_from_direction', 'wind_speed']`
- Claves `next_1_hours.details`: `['precipitation_amount']`
- ¿Aparece `probability_of_precipitation`? **no**
- ¿Aparece `wind_speed_of_gust`? **no**

Ejemplo concreto (convención de intervalos):

```json
[
 {
  "time": "2026-10-03T21:00:00Z",
  "instant": {
   "air_pressure_at_sea_level": 1009.2,
   "air_temperature": 14.6,
   "cloud_area_fraction": 82.8,
   "relative_humidity": 80.0,
   "wind_from_direction": 35.6,
   "wind_speed": 1.8
  },
  "next_1_hours": {
   "summary": {
    "symbol_code": "partlycloudy_day"
   },
   "details": {
    "precipitation_amount": 0.0
   }
  }
 },
 {
  "time": "2026-10-03T22:00:00Z",
  "instant": {
   "air_pressure_at_sea_level": 1009.5,
   "air_temperature": 12.3,
   "cloud_area_fraction": 35.9,
   "relative_humidity": 92.4,
   "wind_from_direction": 43.5,
   "wind_speed": 1.9
  },
  "next_1_hours": {
   "summary": {
    "symbol_code": "fair_night"
   },
   "details": {
    "precipitation_amount": 0.0
   }
  }
 }
]
```
→ `next_1_hours.precipitation_amount` en `time=t` es la lluvia de **[t, t+1h)** (hora que empieza).

- Repetición con `If-Modified-Since: Sat, 03 Oct 2026 21:32:22 GMT` → HTTP **304** (0 bytes, 1.6 s), Expires=`Sat, 03 Oct 2026 22:04:15 GMT`

## C — Alertas SMN (CAP)

- Feed `https://ssl.smn.gob.ar/CAP/AR.php` → HTTP **200** en 1.0 s, 41066 bytes, url final `https://ssl.smn.gob.ar/CAP/AR.php`
- Cabeceras: `{'content-type': 'application/rss+xml; charset=UTF-8', 'server': 'cloudflare', 'cf-ray': 'a44f0f2de976ddab-DFW', 'date': 'Sat, 03 Oct 2026 21:32:25 GMT', 'last-modified': None}`
- Raíz: `rss`
- Ítems en el feed: **68**
- Estructura del primer ítem:
```text
title: TORMENTAS FUERTES CON LLUVIAS INTENSAS, RAFAGAS Y CAIDA DE GRANIZO
link: https://ssl.smn.gob.ar/feeds/CAP/avisocortoplazo/2026_10_03_2116_cap_es.xml
description: Afectando parcialmente los siguientes Partidos y Departamentos: FORMOSA: Formosa - Pirane.
guid: https://ssl.smn.gob.ar/feeds/CAP/avisocortoplazo/2026_10_03_2116_cap_es.xml
pubDate: 
```
- CAP 1 (0.8 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.03.21.16.00` sent=`2026-10-03T21:16:00-03:00` infos=1 campos=`{'event': 'TORMENTAS FUERTES', 'severity': 'Severe', 'urgency': 'Immediate', 'certainty': 'Observed', 'onset': '', 'effective': '', 'expires': '2026-10-03T22:16:00-03:00', 'headline': 'AVISO NARANJA POR TORMENTAS FUERTES CON LLUVIAS INTENSAS, RAFAGAS Y CAIDA DE GRANIZO', 'senderName': 'SERVICIO METEOROLOGICO NACIONAL - ARGENTINA'}` áreas=`['FORMOSA: FORMOSA - PIRANE.  (1 polígonos)']` **contiene el apiario: no**
- CAP 2 (0.8 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.03.21.20.00` sent=`2026-10-03T21:20:00-03:00` infos=1 campos=`{'event': 'TORMENTAS FUERTES', 'severity': 'Severe', 'urgency': 'Immediate', 'certainty': 'Observed', 'onset': '', 'effective': '', 'expires': '2026-10-03T22:20:00-03:00', 'headline': 'AVISO NARANJA POR TORMENTAS FUERTES CON LLUVIAS INTENSAS Y RAFAGAS', 'senderName': 'SERVICIO METEOROLOGICO NACIONAL - ARGENTINA'}` áreas=`['CHACO:  GRAL DONOVAN - 1 DE MAYO - BERMEJO - LIBERTAD - SAN  (1 polígonos)']` **contiene el apiario: no**
- CAP 3 (0.8 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.03.21.28.00` sent=`2026-10-03T21:28:00-03:00` infos=1 campos=`{'event': 'TORMENTAS FUERTES', 'severity': 'Severe', 'urgency': 'Immediate', 'certainty': 'Observed', 'onset': '', 'effective': '', 'expires': '2026-10-03T22:28:00-03:00', 'headline': 'AVISO NARANJA POR TORMENTAS FUERTES CON LLUVIAS INTENSAS, RAFAGAS Y CAIDA DE GRANIZO', 'senderName': 'SERVICIO METEOROLOGICO NACIONAL - ARGENTINA'}` áreas=`['FORMOSA: FORMOSA - PILCOMAYO.  (1 polígonos)']` **contiene el apiario: no**
- CAP 4 (0.8 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.03.20.29.00` sent=`2026-10-03T20:29:00-03:00` infos=1 campos=`{'event': 'TORMENTAS FUERTES', 'severity': 'Severe', 'urgency': 'Immediate', 'certainty': 'Observed', 'onset': '', 'effective': '', 'expires': '2026-10-03T22:29:00-03:00', 'headline': 'AVISO NARANJA POR TORMENTAS FUERTES CON LLUVIAS INTENSAS Y OCASIONAL CAIDA DE GRANIZO', 'senderName': 'SERVICIO METEOROLOGICO NACIONAL - ARGENTINA'}` áreas=`['CHACO: 25 DE MAYO - MAYOR L.  J.  FONTANA - O HIGGINS - SAN  (1 polígonos)']` **contiene el apiario: no**
- CAP 5 (0.3 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.03.20.14.00` sent=`2026-10-03T20:14:00-03:00` infos=1 campos=`{'event': 'TORMENTAS FUERTES', 'severity': 'Severe', 'urgency': 'Immediate', 'certainty': 'Observed', 'onset': '', 'effective': '', 'expires': '2026-10-03T22:14:00-03:00', 'headline': 'AVISO NARANJA POR TORMENTAS FUERTES CON LLUVIAS INTENSAS, RAFAGAS Y OCASIONAL CAIDA DE GRANIZO', 'senderName': 'SERVICIO METEOROLOGICO NACIONAL - ARGENTINA'}` áreas=`['MISIONES: 25 DE MAYO - CAINGUAS - CANDELARIA - LEANDRO N.  A (1 polígonos)']` **contiene el apiario: no**
- CAP 6 (0.3 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.03.20.33.00` sent=`2026-10-03T20:33:00-03:00` infos=1 campos=`{'event': 'TORMENTAS FUERTES', 'severity': 'Severe', 'urgency': 'Immediate', 'certainty': 'Observed', 'onset': '', 'effective': '', 'expires': '2026-10-03T22:33:00-03:00', 'headline': 'AVISO NARANJA POR TORMENTAS FUERTES CON LLUVIAS INTENSAS, RAFAGAS Y CAIDA DE GRANIZO', 'senderName': 'SERVICIO METEOROLOGICO NACIONAL - ARGENTINA'}` áreas=`['FORMOSA: FORMOSA - LAISHI.  (1 polígonos)']` **contiene el apiario: no**
- CAP 7 (0.3 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.03.21.04.00` sent=`2026-10-03T21:04:00-03:00` infos=1 campos=`{'event': 'TORMENTAS FUERTES', 'severity': 'Severe', 'urgency': 'Immediate', 'certainty': 'Observed', 'onset': '', 'effective': '', 'expires': '2026-10-03T22:04:00-03:00', 'headline': 'AVISO NARANJA POR TORMENTAS FUERTES CON LLUVIAS INTENSAS, RAFAGAS Y OCASIONAL CAIDA DE GRANIZO', 'senderName': 'SERVICIO METEOROLOGICO NACIONAL - ARGENTINA'}` áreas=`['MISIONES: 25 DE MAYO - CAINGUAS - GUARANI - LDOR GRAL SAN MA (1 polígonos)']` **contiene el apiario: no**
- CAP 8 (0.3 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.03.21.12.00` sent=`2026-10-03T21:12:00-03:00` infos=1 campos=`{'event': 'TORMENTAS FUERTES', 'severity': 'Severe', 'urgency': 'Immediate', 'certainty': 'Observed', 'onset': '', 'effective': '', 'expires': '2026-10-03T22:12:00-03:00', 'headline': 'AVISO NARANJA POR TORMENTAS FUERTES CON LLUVIAS INTENSAS, RAFAGAS Y OCASIONAL CAIDA DE GRANIZO', 'senderName': 'SERVICIO METEOROLOGICO NACIONAL - ARGENTINA'}` áreas=`['FORMOSA: FORMOSA - LAISHI.  (1 polígonos)']` **contiene el apiario: no**
- CAP 9 (0.3 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.03.20.07.00` sent=`2026-10-03T20:07:00-03:00` infos=1 campos=`{'event': 'TORMENTAS FUERTES', 'severity': 'Severe', 'urgency': 'Immediate', 'certainty': 'Observed', 'onset': '', 'effective': '', 'expires': '2026-10-03T22:07:00-03:00', 'headline': 'AVISO NARANJA POR TORMENTAS FUERTES CON LLUVIAS INTENSAS Y OCASIONAL CAIDA DE GRANIZO', 'senderName': 'SERVICIO METEOROLOGICO NACIONAL - ARGENTINA'}` áreas=`['FORMOSA: PATINO. CHACO: GRAL GUEMES - LDOR GRAL S.  MARTIN.  (1 polígonos)']` **contiene el apiario: no**
- CAP 10 (0.8 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.03.20.11.00` sent=`2026-10-03T20:11:00-03:00` infos=1 campos=`{'event': 'TORMENTAS FUERTES', 'severity': 'Severe', 'urgency': 'Immediate', 'certainty': 'Observed', 'onset': '', 'effective': '', 'expires': '2026-10-03T22:11:00-03:00', 'headline': 'AVISO NARANJA POR TORMENTAS FUERTES CON LLUVIAS INTENSAS Y OCASIONAL CAIDA DE GRANIZO', 'senderName': 'SERVICIO METEOROLOGICO NACIONAL - ARGENTINA'}` áreas=`['CHACO: SAN FERNANDO - TAPENAGA. SANTA FE: GRAL OBLIGADO - VE (1 polígonos)']` **contiene el apiario: no**
- CAP 11 (0.8 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.03.20.39.52.8` sent=`2026-10-03T20:39:52-03:00` infos=1 campos=`{'event': 'Nevadas', 'severity': 'Moderate', 'urgency': 'Immediate', 'certainty': 'Likely', 'onset': '2026-10-03T20:39:52-03:00', 'effective': '', 'expires': '2026-10-04T14:59:59-03:00', 'headline': 'Nevadas', 'senderName': 'Servicio Meteorologico Nacional'}` áreas=`[' (1 polígonos)']` **contiene el apiario: no**
- CAP 12 (0.3 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.03.20.39.52.7` sent=`2026-10-03T20:39:52-03:00` infos=1 campos=`{'event': 'Nevadas', 'severity': 'Moderate', 'urgency': 'Immediate', 'certainty': 'Likely', 'onset': '2026-10-03T20:39:52-03:00', 'effective': '', 'expires': '2026-10-03T20:59:59-03:00', 'headline': 'Nevadas', 'senderName': 'Servicio Meteorologico Nacional'}` áreas=`[' (1 polígonos)']` **contiene el apiario: no**
- CAP 13 (0.3 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.03.20.39.50.2` sent=`2026-10-03T20:39:50-03:00` infos=1 campos=`{'event': 'Viento', 'severity': 'Moderate', 'urgency': 'Immediate', 'certainty': 'Likely', 'onset': '2026-10-03T20:39:50-03:00', 'effective': '', 'expires': '2026-10-03T20:59:59-03:00', 'headline': 'Viento', 'senderName': 'Servicio Meteorologico Nacional'}` áreas=`[' (1 polígonos)']` **contiene el apiario: no**
- CAP 14 (0.3 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.03.20.39.52.6` sent=`2026-10-03T20:39:52-03:00` infos=1 campos=`{'event': 'Nevadas', 'severity': 'Moderate', 'urgency': 'Immediate', 'certainty': 'Likely', 'onset': '2026-10-03T20:39:52-03:00', 'effective': '', 'expires': '2026-10-03T20:59:59-03:00', 'headline': 'Nevadas', 'senderName': 'Servicio Meteorologico Nacional'}` áreas=`[' (1 polígonos)']` **contiene el apiario: no**
- CAP 15 (0.3 s): identifier=`urn:oid:2.49.0.1.32.0.2026.10.03.20.39.50.1` sent=`2026-10-03T20:39:50-03:00` infos=1 campos=`{'event': 'Viento', 'severity': 'Moderate', 'urgency': 'Immediate', 'certainty': 'Likely', 'onset': '2026-10-03T20:39:50-03:00', 'effective': '', 'expires': '2026-10-03T20:59:59-03:00', 'headline': 'Viento', 'senderName': 'Servicio Meteorologico Nacional'}` áreas=`[' (1 polígonos)']` **contiene el apiario: no**

## D — Open-Meteo

No consultada: el usuario indicó dejarla **apagada** (uso que no califica como no comercial). Sin datos de verificación.

## Resumen

- `smn_wrf`: ok
- `metno`: ok
- `smn_cap`: ok
