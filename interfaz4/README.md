# Interfaz 4 — Contexto meteorológico para visitas a apiarios

Doble vía:

- **Ida (humano → motor):** quien va a visitar el apiario registra la visita
  (apiario, fecha y rango horario) desde
  **[Interfaz 4](https://eduabejas.github.io/apiario-portal/interfaz4.html)**.
- **Vuelta (motor → humano):** **24 h y 12 h antes** del inicio, el motor
  consulta fuentes meteorológicas públicas y gratuitas para esa ventana y
  manda la información organizada por **correo** (y por Google Chat, si se
  habilita).

> **Organizar, no interpretar.** El motor solo recopila, normaliza, agrega
> (mín/máx/suma) y presenta. No hay recomendaciones, "buen/mal día",
> semáforos ni resúmenes con IA. Cada valor se puede rastrear a su fuente,
> su hora de validez y el ciclo/emisión del modelo. Lo que falta se muestra
> como `s/d`.

## Cómo se usa

1. Entrá a **Interfaz 4** desde el portal (o directo:
   <https://eduabejas.github.io/apiario-portal/interfaz4.html>).
2. Completá fecha, horario, responsable y notas, y tocá **Registrar en
   GitHub**. Se abre GitHub con la visita precargada: tocá **Create**.
3. En ~1 minuto el workflow de registro agenda la visita, responde en el
   issue con los horarios de los informes y lo cierra. La visita aparece en
   Interfaz 4 con el estado de cada informe.
4. A su hora llegan los informes por correo. También se pueden ver desde
   Interfaz 4 (**Ver informe**), idénticos al correo.
5. Para cancelar: botón **Cancelar visita** en Interfaz 4 (abre otro issue
   precargado).

Hace falta tener sesión en GitHub con la cuenta dueña del repositorio o una
cuenta **colaboradora** (Settings → Collaborators). Los issues de otras
cuentas se cierran sin cambios: así nadie de afuera puede agendar correos.

## Puesta en marcha (una sola vez)

### 1. Contraseña de aplicación de Gmail

El motor manda los correos desde una cuenta de Gmail con una *contraseña de
aplicación* (no la contraseña normal):

1. En la cuenta de Google que va a enviar, activá la **verificación en 2
   pasos** (<https://myaccount.google.com/security>).
2. Entrá a <https://myaccount.google.com/apppasswords>, creá una con el
   nombre "Interfaz 4" y copiá los 16 caracteres (los espacios no importan).

### 2. Secretos del repositorio

En GitHub: **Settings → Secrets and variables → Actions → New repository
secret**. Nunca se escriben en el código ni en `datos/`.

| Secreto | Obligatorio | Ejemplo / uso |
|---|---|---|
| `SMTP_USUARIO` | sí | `cuenta@gmail.com` (la que envía) |
| `SMTP_CLAVE_APP` | sí | la contraseña de aplicación |
| `CORREO_DESTINO_POR_DEFECTO` | sí | quién recibe los informes; admite varios separados por coma |
| `CORREOS_RESPONSABLES` | no | correo por responsable: `Eduardo Mendoza=edu@x.com; Rocío Barni=rocio@y.com` (si el nombre de la visita coincide, se usa ese correo) |
| `SMTP_REMITENTE` | no | remitente visible, p. ej. `Interfaz 4 · Apiario <cuenta@gmail.com>` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_SEGURIDAD` | no | por defecto `smtp.gmail.com`, `587`, `starttls` (con `465` usa SSL) |
| `METNO_USER_AGENT` | no | identificación ante MET Norway; por defecto `interfaz4-apiarios/0.1 (+https://github.com/eduabejas/apiario-portal)` |
| `GCHAT_WEBHOOK_URL` | no | solo con Google Workspace y el canal habilitado en `config/ajustes.yaml` |

### 3. Probar

- **Actions → "Interfaz 4 — motor de informes" → Run workflow → `probar-fuentes`**:
  muestra el estado de cada fuente y si el correo está configurado.
- Registrá una visita de prueba para mañana. Si está a menos de 24 h, el
  informe de 24 h sale en unos minutos (el registro dispara el motor).
- Si un correo falla (p. ej. faltan secretos), Interfaz 4 lo muestra como
  "No se pudo enviar" con el motivo, y el motor lo reintenta cada hora
  mientras ese informe siga vigente.

## Fuentes (todas gratuitas, sin API key)

| Fuente | Rol | Variables | Licencia |
|---|---|---|---|
| **SMN WRF** (AWS Open Data, `s3://smn-ar-wrf`) | principal | temperatura, humedad, viento y dirección, lluvia horaria (4 km) | CC BY 2.5 AR |
| **MET Norway** Locationforecast 2.0 | contraste | temperatura, humedad, viento y dirección, lluvia horaria | CC BY 4.0 |
| **Alertas SMN** (CAP) | alertas oficiales | texto copiado tal cual, solo si el polígono contiene al apiario y la vigencia se superpone con la visita | CC BY 4.0 |
| Open-Meteo | **apagada** | probabilidad y ráfagas | gratis solo para uso no comercial |
| ECMWF ENS | apagada (Fase 7) | % de miembros con lluvia | CC BY 4.0 |

Probabilidad de lluvia y ráfagas: ni SMN WRF ni MET Norway las publican para
Argentina, por eso aparecen como `s/d`. Detalles verificados (ciclos,
convenciones de intervalos, bytes, formatos CAP) en
[`docs/verificacion_fuentes.md`](docs/verificacion_fuentes.md).

**Convención de intervalos:** cada fila H del informe es el intervalo
[H, H+1h) en hora Argentina. Temperatura, humedad y viento son los valores
en H; la lluvia es la acumulada en [H, H+1h) (en el WRF sale del archivo
válido en H+1; en MET Norway, de `next_1_hours` en H).

## El informe

1. Encabezado: apiario y coordenada, fecha y ventana, responsable, notas,
   momento de generación y del próximo informe.
2. Alertas SMN vigentes para el punto y la ventana (texto textual), o "Sin
   alertas…" / "no disponibles en esta ejecución".
3. Resumen de la ventana por fuente: temperatura y humedad mín/máx, viento
   máximo y rumbo, ráfaga máxima, lluvia total, probabilidad máxima.
4. Antes de la visita: lluvia prevista desde el envío hasta el inicio.
5. Detalle horario por fuente.
6. En el de 12 h: diferencias numéricas respecto al de 24 h.
7. Fuentes, ciclo/emisión, licencias y la leyenda fija: *"Este informe
   presenta datos de pronóstico sin interpretación. Las decisiones quedan a
   criterio de quien visita el apiario."*

Asunto: `🐝 Visita {apiario} {dd/mm} {desde}–{hasta} · informe {24|12} h`.

## Automatización (GitHub Actions)

| Workflow | Cuándo | Qué hace |
|---|---|---|
| `interfaz4.yml` — motor | cada hora (min 17) y manual | `interfaz4 ejecutar`: envía los hitos vencidos, actualiza `state/` y `publico/` y los commitea (`chore(estado): envíos …`) |
| `interfaz4-registro.yml` | al abrir/editar un issue de Interfaz 4 | valida y guarda la visita en `datos/visitas.yaml`, responde, cierra el issue y dispara el motor |
| `interfaz4-ci.yml` | push / PR | tests de Python y de la web |
| `interfaz4-verificar.yml` | manual | vuelve a verificar las fuentes desde Actions (Fase 0) |

**Forzar una ejecución:** Actions → "Interfaz 4 — motor de informes" → Run
workflow.

**Confiabilidad del cron:** el `schedule` de GitHub es *best effort* y a veces
se demora o saltea ejecuciones. La regla "hito vencido y no enviado" lo
absorbe: el informe sale en la primera ejecución posterior. Como redundancia
gratuita se puede:

- disparar el workflow desde un cron externo con un token *fine-grained*
  (permiso *Actions: write* solo en este repo):
  ```bash
  curl -X POST -H "Authorization: Bearer $TOKEN" \
    https://api.github.com/repos/eduabejas/apiario-portal/actions/workflows/interfaz4.yml/dispatches \
    -d '{"ref":"main"}'
  ```
- o correr el motor en una PC/Raspberry Pi siempre encendida con `cron`
  (`17 * * * * cd ~/apiario-portal/interfaz4 && git pull -q && uv run interfaz4 ejecutar && git add state datos publico && git commit -qm "chore(estado): envíos" && git push -q`).

## CLI (uso local)

Requiere Python 3.12 y [uv](https://docs.astral.sh/uv/). Desde `interfaz4/`:

```bash
uv sync                      # instala dependencias
cp .env.example .env         # completar SMTP_* y CORREO_DESTINO_POR_DEFECTO (no se commitea)

uv run interfaz4 planificar --apiario produccion_miel --fecha 2026-10-10 --desde 09:00 --hasta 13:00 \
                            --responsable "Nombre" [--correo persona@dominio.com] [--chat] [--notas "..."]
uv run interfaz4 listar [--todas]
uv run interfaz4 cancelar <id>
uv run interfaz4 informe <id> --hito 24 [--enviar | --vista-previa salida.html]
uv run interfaz4 ejecutar [--ahora 2026-10-09T09:17-03:00]   # --ahora solo para pruebas
uv run interfaz4 probar-fuentes
uv run interfaz4 publicar                                     # regenera publico/ para la web
```

`--correo` existe para uso local; en este repositorio público conviene
resolver los destinatarios con los secretos.

## Configuración

- `config/apiarios.yaml`: apiarios y coordenadas. El de **cría de reinas**
  queda comentado: es parte de otro proyecto que empieza en 2027. Al
  sumarlo, agregar también la opción en
  `.github/ISSUE_TEMPLATE/interfaz4-visita.yml`.
- `config/ajustes.yaml`: hitos (24/12 h), fuentes y canales habilitados,
  tramo previo, comparación 24→12, reintentos HTTP.
- `datos/visitas.yaml`: visitas (las escribe el registro por issues o la CLI).
- `state/`: `envios.json` (idempotencia), `cache_grilla.json` (punto de
  grilla del WRF) y `snapshots/` (datos de cada informe, para comparar 24→12).
- `publico/`: lo que lee la web (`estado.json` sin correos e informes HTML).

## Privacidad

El repositorio es **público** (GitHub Pages gratis lo requiere). Por eso:
los correos y claves viven solo en *Secrets*; `datos/`, `state/` y `publico/`
no guardan correos. Sí quedan públicos la coordenada del apiario, fecha y
horario de las visitas, el nombre del responsable y las notas: no escribas
ahí nada sensible.

## Desarrollo

```bash
cd interfaz4 && uv run pytest --cov=interfaz4   # motor (tests offline con datos reales capturados)
cd .. && npm test                                # lógica de la web (node --test)
```

Los tests no salen a la red: usan un recorte real del WRF
(`tests/fixtures/smn_wrf`, generado con `scripts/generar_fixture_wrf.py`) y
respuestas reales de MET Norway y del SMN capturadas en la Fase 0
(`scripts/verificar_fuentes.py`).

Estructura:

```
interfaz4/
├── config/ datos/ state/ publico/ docs/ scripts/ tests/
└── src/interfaz4/
    ├── cli.py config.py modelos.py tiempo.py normalizar.py
    ├── planificador.py estado.py motor.py publicar.py issues.py
    ├── visitas/   (base.py, archivo_yaml.py)
    ├── fuentes/   (smn_wrf.py, metno.py, smn_cap.py, open_meteo.py, http.py)
    ├── informe/   (recoleccion.py, constructor.py, plantillas/*.j2)
    └── notificar/ (correo_smtp.py, google_chat.py)
```

## Problemas comunes

- **"No se pudo enviar · correo sin configurar"**: faltan `SMTP_USUARIO` /
  `SMTP_CLAVE_APP` en los secretos.
- **"el servidor SMTP rechazó usuario/clave"**: en Gmail hace falta la
  contraseña de aplicación (paso 1), no la contraseña de la cuenta.
- **"sin destinatarios"**: cargar `CORREO_DESTINO_POR_DEFECTO`.
- **El issue no se procesa**: tiene que crearlo la cuenta dueña o una
  colaboradora, y el título tiene que empezar con "Interfaz 4 · ".
- **"Alertas SMN no disponibles en esta ejecución"**: el feed CAP no
  respondió o pidió verificación anti-bot. No se evade; el informe sigue con
  las demás fuentes.
