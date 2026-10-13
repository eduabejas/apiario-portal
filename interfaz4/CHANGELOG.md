# CHANGELOG — Interfaz 4

## 1.1.0 — 2026-10-13

- Precipitación nunca se oculta como `0,0`: `s/d` cuando no hay dato, `<0,1`
  cuando el modelo prevé entre 0 y 0,1 mm, y suma con completitud `N/M h`.
- Mapa de lluvia WRF-SMN inline en el correo (opcional, bajo flag). No
  bloquea el envío si falla; adjunta por CID (Gmail no acepta `data:` URI).
- Lista blanca de hosts, tope de 5 MB por respuesta y validación de TLS en
  el cliente HTTP; `PuntoHorario` con `extra="forbid"`.
