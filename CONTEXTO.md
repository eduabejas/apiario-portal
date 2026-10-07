# Portal Apiario — Contexto para Claude Code

## Objetivo
Migrar el portal de Google Apps Script a un frontend estático en **GitHub
Pages**, manteniendo la paleta visual (miel/ámbar) y la funcionalidad de
enrutamiento, con mejor DX y sin dependencia de Apps Script para el
frontend.

---

## Estado de migración
- [x] `index.html` — Portal de selección (usuario + interfaz)
- [x] `interfaz1.html` — Mapas y ambiente (terreno 3D + vista satelital,
      portado desde `colmena-portal/src/Interfaz1.html`)
- [x] `interfaz2.html` — Datos y precios (placeholder restyleado)
- [x] `interfaz3.html` — Bitácora de colmenas (revisión + vista QR, alpha1)
- [x] `assets/styles.css` — Tailwind v4 compilado y purgado
- [x] `assets/alpine.min.js` — Alpine.js v3 (build `cdn.min.js`)
- [x] `assets/data/terreno-3d.json`, `assets/data/overlay.json` — datos
      del relieve extraídos de `DatosTerreno.html` / `DatosOverlay.html`
- [x] `assets/media/satelital.jpg` — imagen satelital extraída de
      `DatosSatelital.html` (antes embebida en base64)
- [x] GitHub Actions deploy a Pages configurado (`.github/workflows/pages.yml`)
- [ ] Activar Pages en Settings → Pages → Source: **GitHub Actions** (paso
      manual único, no se puede hacer desde acá)
- [ ] Interfaz 2: leer/graficar hojas de `Apiario_DB` (Chart.js)
- [x] ~~Interfaz 3: formulario de revisión → endpoint `doPost` en Apps Script~~
      (`apps-script/bitacora/Code.gs`, deploy manual — ver pasos del alpha1)
- [x] `interfaz4.html` — Contexto meteorológico de visitas (ida: formulario →
      issue de GitHub; vuelta: estado e informes que publica el motor)
- [x] `interfaz4/` — motor Python (Fases 0–6 de la spec): fuentes SMN WRF,
      MET Norway y alertas CAP; informes 24 h / 12 h por correo vía
      GitHub Actions (ver `interfaz4/README.md`)
- [ ] Interfaz 4: cargar los secretos SMTP en GitHub (paso manual, ver
      `interfaz4/README.md` → Puesta en marcha)
- [x] `bitacoraderevision/` — Bitácora de revisión (registros, nueva
      revisión con varroa/acaricida y pestaña «Mapa» del apiario), importada
      de `ApisAgroecologicaPredio6Agosto/bitacoraderevision` y publicada en
      `/bitacoraderevision/`
- [ ] Bitácora de revisión: crear la hoja + implementar
      `bitacoraderevision/apps-script/Codigo.gs` y pegar la URL en
      `bitacoraderevision/assets/config.js` (paso manual, ver su README)

---

## Repo destino
Este mismo repo (`apiario-portal`). El sitio estático vive en la **raíz**;
`colmena-portal/` queda como el origen Apps Script (ver más abajo) y no se
publica en Pages (el workflow solo copia `index.html`, `interfaz*.html` y
`assets/` a `_site/`).

---

## Estructura actual
```
/
├── index.html            # Portal (selección usuario + interfaz)
├── interfaz1.html        # Mapas / terreno 3D / satelital + crecida
├── interfaz2.html        # Datos, precios, gráficos (placeholder)
├── interfaz3.html        # Bitácora de revisión de colmenas (placeholder)
├── interfaz4.html        # Contexto meteorológico de visitas (formulario + estado de informes)
├── interfaz4/            # Motor Python de Interfaz 4 (GitHub Actions, ver su README)
├── bitacoraderevision/   # Bitácora de revisión + mapa del apiario: sitio autocontenido
│                         # (HTML/CSS/JS sin build ni Tailwind, backend propio en
│                         # apps-script/Codigo.gs; ver su README)
├── sw.js                 # Service worker de la bitácora (cache-first solo de su shell)
├── manifest.webmanifest  # PWA de la bitácora (start_url interfaz3.html)
├── assets/
│   ├── styles.css        # Tailwind v4 compilado (npm run build:css)
│   ├── alpine.min.js     # Alpine.js v3
│   ├── js/
│   │   ├── usuarios.js       # Catálogo de usuarios/interfaces (antes en Code.gs)
│   │   ├── portal.js         # Lógica del formulario del portal + marcador ?u=&i=
│   │   ├── topbar.js         # Chip de usuario en interfaz2/3/bitácora
│   │   ├── bitacora-core.js  # Funciones puras de la bitácora (testeadas con node --test)
│   │   ├── bitacora.js       # Store Alpine + outbox + fetch + animaciones GSAP
│   │   ├── bitacora-config.js# ENDPOINT y APP_VERSION de la bitácora
│   │   ├── interfaz4-core.js # Funciones puras de Interfaz 4 (testeadas con node --test)
│   │   ├── interfaz4.js      # Componente Alpine de Interfaz 4
│   │   └── interfaz4-config.js # Repo y URLs de datos de Interfaz 4
│   ├── vendor/
│   │   ├── gsap.min.js       # GSAP 3, vendorizado (npm run vendor)
│   │   └── qrcode.js         # qrcode-generator, vendorizado (npm run vendor)
│   ├── icons/
│   │   └── bitacora.svg      # Ícono PWA (hexágono miel)
│   ├── data/
│   │   ├── terreno-3d.json
│   │   └── overlay.json
│   └── media/
│       └── satelital.jpg
├── apps-script/bitacora/Code.gs  # Backend de la bitácora (doGet/doPost), deploy manual aparte
├── tests/bitacora-core.test.js   # node --test
├── src/tailwind.css      # Fuente del build de Tailwind (paleta miel, tonos, glass, fondo animado)
├── package.json          # devDependencies: tailwindcss + cli; deps: alpinejs, gsap, qrcode-generator
├── .nojekyll
├── .github/workflows/
│   ├── deploy.yml        # Deploy Apps Script (colmena-portal/** → clasp)
│   ├── pages.yml         # Deploy GitHub Pages (index/interfaz*/assets/sw/manifest/bitacoraderevision → Pages)
│   ├── interfaz4.yml     # Motor de Interfaz 4 (cada hora)
│   ├── interfaz4-registro.yml  # Issues "Interfaz 4 · …" → datos/visitas.yaml
│   ├── interfaz4-ci.yml  # Tests de Interfaz 4 (Python + node --test)
│   └── interfaz4-verificar.yml # Verificación de fuentes (manual)
└── colmena-portal/       # Origen Apps Script del portal (ver colmena-portal/README.md)
```

**Para regenerar el CSS** después de tocar clases nuevas en los HTML o en
`src/tailwind.css`:
```bash
npm install   # una vez
npm run build:css
```

---

## Enrutamiento (cliente, sin backend)
- `index.html` → Portal de selección
- Submit del form → `interfazN.html?u=<slug>`
- Marcador de acceso directo: `index.html?u=rocio&i=3` redirige solo con JS
  a `interfaz3.html?u=rocio` (equivalente al viejo `/exec?u=rocio&i=3`)
- Cada `interfazN.html` lee `?u=` con `URLSearchParams` para mostrar el
  chip de usuario y el link "← Portal"
- Catálogo de usuarios/interfaces vive en `assets/js/usuarios.js`
  (`window.APIARIO_USUARIOS`, `window.APIARIO_INTERFACES`)

Usuarios: `rocio` (Rocío Barni), `eduardo` (Eduardo Mendoza). Sin
contraseñas, acceso por URL pública.

---

## Diseño visual
- Paleta miel/ámbar vía `@theme` de Tailwind (`--color-miel`,
  `--color-miel-dark`, `--color-cera`, `--color-tinta`, `--color-gris`,
  `--color-borde`), definida en `src/tailwind.css`
- Glassmorphism con CSS puro: clase `.glass-card` (blur + fondo
  semitransparente), sin dependencias extra
- Fondo animado con CSS puro: `.honey-bg` (dos manchas de color con blur
  que se mueven lento) — reemplaza el GIF/MP4 sugerido en el brief
  original mientras no haya media propia del apiario para embeber;
  respeta `prefers-reduced-motion`
- Interfaz 1 mantiene su propio tema oscuro tipo "instrumento de campo"
  (no usa Tailwind/Alpine, es autocontenida — así estaba en el original)

---

## Interfaz 1 — cómo quedó portada
El archivo original (`colmena-portal/src/Interfaz1.html`, Three.js +
canvas 2D) se copió tal cual y se le sacó la dependencia de Apps Script:
- `<?= baseUrl ?>` → `href="index.html"`
- `<?= usuario.nombre ?>` → chip poblado en runtime leyendo `?u=` vía
  `assets/js/usuarios.js`
- `<?!= include('DatosTerreno') ?>` / `DatosOverlay` (arrays JSON enormes
  embebidos inline) → `fetch('assets/data/terreno-3d.json')` /
  `fetch('assets/data/overlay.json')`
- `<?!= include('DatosSatelital') ?>` (imagen embebida en base64, ~428KB
  de texto) → `assets/media/satelital.jpg` (321KB binario real),
  asignada directo a `img.src`

Tres.js y OrbitControls se siguen cargando desde CDN (cdnjs/jsdelivr),
sin cambios.

---

## Usuarios
| Nombre | Slug | Rol |
|--------|------|-----|
| Rocío Barni | `rocio` | Administrador |
| Eduardo Mendoza | `eduardo` | Administrador |

---

## Reglas para Claude Code
1. No usar Apps Script para el frontend — todo HTML/CSS/JS estático
2. Mantener Tailwind + Alpine como sistema de componentes
3. Links a Sheets son directos — no OAuth ni Google API client
4. Media (imágenes/video): comprimir antes de commitear
5. Sin frameworks pesados salvo pedido explícito (React, Vue, etc.)
6. Un archivo HTML por interfaz — sin rutas dinámicas complejas
7. Animaciones: GSAP (vendorizado en `assets/vendor/`) permitido; CSS para lo trivial

---

## Notas
- Falta un paso manual único: en GitHub → Settings → Pages → Source,
  elegir **GitHub Actions** (el workflow `pages.yml` ya está listo, pero
  necesita que la fuente esté configurada así para poder desplegar)
- Límite práctico de Pages: 1&nbsp;GB del sitio — los assets actuales
  (~950KB entre datos + imagen satelital) están lejos de ese límite
- `colmena-portal/` se mantiene como está: es el origen Apps Script y
  sigue teniendo su propio deploy (`deploy.yml` → clasp). Si más adelante
  Interfaz 2/3 necesitan leer o escribir en `Apiario_DB`, ese Apps Script
  puede exponerse como endpoint JSON (`doGet`/`doPost`) sin volver a
  depender de Apps Script para servir HTML
