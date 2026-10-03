# Fase 0 — Verificación de fuentes

Verificación hecha el **03/10/2026** para la coordenada del apiario
(-34.889180362505506, -57.82789829443907), desde **GitHub Actions** (el
entorno real de ejecución) con `scripts/verificar_fuentes.py`. La salida
completa de cada corrida queda en
[`verificacion_fuentes_ejecucion.md`](verificacion_fuentes_ejecucion.md) y
las respuestas reales en `tests/fixtures/` (copias congeladas que usan los
tests) y `tests/fixtures/ultima_verificacion/` (última corrida).

Resultado: **las tres fuentes habilitadas devuelven datos para la
coordenada**. Open-Meteo no se consultó (apagada por decisión del usuario).

| Fuente | Estado | Observación principal |
|---|---|---|
| A — SMN WRF (s3://smn-ar-wrf) | ✅ | Punto de grilla (iy=621, ix=662) a 1,72 km. Lectura de un punto ≈ 15 MB por archivo (5 variables). |
| B — MET Norway compact | ✅ | HTTP 200 (gzip) y 304 con `If-Modified-Since`. Sin probabilidad ni ráfagas. |
| C — Alertas SMN (CAP) | ✅ | Feed detrás de Cloudflare pero **sin challenge** desde GitHub Actions (HTTP 200). |
| D — Open-Meteo | — | No consultada: el uso no califica como no comercial (decisión del usuario). |
| E — ECMWF ENS | — | Fase 7 (apagada). Medido: ~42 MB por paso de 3 h para `tp` de 50 miembros. |

## A — SMN WRF-SMN determinístico

- **Ciclos**: 00, 06, 12 y 18 UTC, todos completos en las últimas 48 h.
  Cada ciclo se publica **2,0–2,7 h después** de su hora de inicio y los
  archivos se suben de forma progresiva durante ~15 min.
- **Plazos**: `000`–`072` (73 archivos horarios por ciclo).
  *Diferencia con la spec*: el documento decía "000–073"; el último plazo
  publicado es `072`.
- Además de `01H` hay archivos `10M` (precipitación cada 10 min, 6 pasos por
  archivo) y `24H` (Tmin/Tmax diarias). No se usan.
- **Archivo**: NetCDF4/HDF5 de ~37 MB, grilla `y=1249 × x=999`, `lat`/`lon`
  2D, un solo tiempo válido en `init + PPP h` (`time` en
  `hours since <init>`).
- **Variables** confirmadas: `T2` (°C, calibrada), `HR2` (%), `magViento10`
  (m/s, calibrada), `dirViento10` (°), `PP` (mm).
- **Chunks**: cada variable es **un único chunk** de toda la grilla con
  zlib + shuffle (2,6–3,8 MB comprimido; `PP` ~1,7 MB). Leer un punto obliga
  a bajar el chunk completo de cada variable.
- **Bytes y tiempos** (desde GitHub Actions):
  - con `xarray` + `h5netcdf` + `isel`: 121 lecturas, 18,0 MB, 8,8 s por
    archivo (lee coordenadas y atributos que no hacen falta);
  - con **`h5py` directo sobre `s3fs`** (`cache_type="none"`): 23 pedidos,
    ~15 MB, ~2 s por archivo; solo `PP`: ~2 MB.
  - *Diferencia con la spec*: se implementó con `h5py` (es la capa que usa
    `h5netcdf` por debajo) porque mide 5 veces menos pedidos. `xarray` queda
    solo para los scripts de verificación.
- **Semántica de `PP`**: aunque el `long_name` dice "Accumulated Total
  Precipitation", **no** es acumulada desde el inicio: en 43 375 puntos
  `PP(012) < PP(011)`. Contrastada con los archivos de 10 min, `PP` del
  archivo válido en `t` es exactamente la lluvia de **(t−1h, t]** (error
  medio 2,8·10⁻⁸ mm; la hipótesis [t−1h, t) da 0,94 mm).
  → **Fila H = archivo válido en H+1** (como indica la spec).
- **Punto de grilla**: (iy=621, ix=662), lat -34,89776, lon -57,84357,
  a **1,72 km** del apiario. Se cachea en `state/cache_grilla.json` con la
  forma de la grilla como firma.
- Observaciones de datos: `HR2` puede superar levemente 100 % (100,41) y
  `magViento10` puede ser exactamente 0,0 de noche. Se muestran tal cual
  (sin recortar ni corregir).

Ejemplo concreto (ciclo 03/10 18 UTC, plazo 012, válido 04/10 06 UTC):
`T2=10,63 °C`, `HR2=100,41 %`, `magViento10=0,0 m/s`, `dirViento10=256,9°`,
`PP=0,02 mm` (lluvia entre 05 y 06 UTC).

## B — MET Norway Locationforecast 2.0

- `GET .../compact?lat=-34.8892&lon=-57.8279` con User-Agent
  `interfaz4-apiarios/0.1 (+https://github.com/eduabejas/apiario-portal)` →
  **200** en 1,0 s, 39,8 kB descomprimidos (`content-encoding: gzip`).
- `Expires` ≈ 30 min después del pedido; `Last-Modified` presente. La
  repetición con `If-Modified-Since` devuelve **304** sin cuerpo.
- `meta.updated_at` (emisión del producto): `2026-10-03T19:21:14Z`.
- 90 pasos: **horarios hasta ~+62 h** (63 con `next_1_hours`), después cada
  6 h. Las filas sin paso horario quedan en `s/d`.
- `instant.details`: `air_temperature`, `relative_humidity`, `wind_speed`
  (m/s), `wind_from_direction`, `air_pressure_at_sea_level`,
  `cloud_area_fraction`. `next_1_hours.details`: solo
  `precipitation_amount`.
- **No aparecen** `probability_of_precipitation` ni `wind_speed_of_gust`.
- Convención observada: en `time=2026-10-03T21:00:00Z`,
  `next_1_hours.precipitation_amount=0.0` es la lluvia de **[21:00, 22:00)
  UTC** (hora que empieza) → fila H = timestamp H.

## C — Alertas SMN (CAP)

- Feed `https://ssl.smn.gob.ar/CAP/AR.php` → **200**,
  `application/rss+xml`, `server: cloudflare`, **sin challenge** desde
  GitHub Actions. 68 ítems: 10 `avisocortoplazo` y 58 `xml_generados`.
  `pubDate` de los ítems viene vacío.
- Dos formatos de XML CAP 1.2:
  - **Avisos a corto plazo** (`feeds/CAP/avisocortoplazo/...`): prefijo
    `cap:`, `msgType=Alert`, sin `onset` ni `effective` (la vigencia se toma
    desde `sent`), vencen ~1 h después, `areaDesc` con partidos, un
    polígono.
  - **Alertas por zona** (`feeds/CAP/xml_generados/...`): namespace por
    defecto, `language=es-AR`, `msgType=Update` con `<references>` al aviso
    que reemplazan, `onset`/`expires`, `areaDesc` vacío, un polígono.
    → se descartan las alertas reemplazadas por un `Update` presente en el
    feed.
- Polígonos en formato `lat,lon lat,lon …` (se invierten a `lon,lat` para
  `shapely`). Se usa `covers` (incluye el borde) y se soportan `circle`.
- Ninguna alerta del 03/10 contenía al apiario (eran de Formosa, Chaco,
  Misiones y la cordillera).
- Los textos de instrucciones del SMN incluyen palabras como "evitá" o
  "riesgo": se copian **textuales**, y el test de palabras valorativas
  excluye el texto de las alertas.

## E — ECMWF Open Data ENS (Fase 7, apagada)

Medición del 03/10/2026 sobre `s3://ecmwf-forecasts` (acceso anónimo,
región eu-central-1), corrida `20261003/12z/ifs/0p25/enfo`:

- Un archivo GRIB2 por paso (`…-24h-enfo-ef.grib2`, 6,8 GB con todas las
  variables y miembros) y un `.index` JSON por línea con `_offset` y
  `_length` de cada mensaje: se puede bajar solo `param=tp` de los 50
  miembros perturbados (`type=pf`) con pedidos por rango.
- `tp` de los 50 miembros en un paso: **41,8 MB** (~0,84 MB por miembro,
  grilla global de 0,25°).
- Pasos cada 3 h: una ventana de 4 h necesita 3 pasos → **~125 MB por
  informe** (~250 MB por visita), más la dependencia `eccodes` para
  decodificar GRIB.
- Conclusión: es viable y es la única fuente sin restricción comercial que
  aporta "% de miembros con precipitación ≥ 0,1 mm" (por intervalo de 3 h).
  Queda **apagada** (`fuentes.ecmwf_ens.habilitada: false`) y sin
  implementar en esta entrega; es el próximo paso recomendado si se quiere
  probabilidad de lluvia.

## Entorno

- Desde el contenedor de desarrollo de Claude Code, la política de red
  bloqueó `api.met.no`, `ssl.smn.gob.ar` y `api.open-meteo.com` (sí permitió
  S3). Por eso la verificación corre en GitHub Actions
  (`.github/workflows/interfaz4-verificar.yml`), que es además el entorno
  donde funciona el motor.
