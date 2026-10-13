# CLAUDE.md

## Invariantes de Interfaz 4 (v1.1)

- Precipitación: `None` ≠ `0.0`. `None` = sin dato; `0.0` = el modelo midió 0.
  Nunca inicializar `precip_mm` en 0 ni usar `|default(0)` en plantillas.
- Convención de intervalos: fila H = [H, H+1h) en hora local Argentina.
  WRF `PP` → archivo H+1 · MET `next_1_hours` → timestamp H · Open-Meteo → H+1.
  Usar `tiempo.clave_hora(dt)` como clave canónica (prohíbe naive).
- Nunca descargar archivos WRF completos: cada archivo pesa 30–40 MB y se
  lee por rangos con `s3fs` + `h5py`.
- Modelos internos: `model_config = ConfigDict(extra="forbid")`.
- Plantillas Jinja: `undefined=StrictUndefined`.
- Red: solo HTTPS a hosts de `HOSTS_PERMITIDOS` (interfaz4.fuentes.http).
  Tope de 5 MB por respuesta. Redirecciones fuera de la lista se rechazan.
- Mapa (`v1.1`): usa `PP` del WRF que ya se lee para el detalle. Jamás
  bloquea el envío del correo; una excepción solo deja el bloque fuera.
