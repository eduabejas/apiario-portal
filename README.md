# apiario-portal

Portal único para el proyecto de apiario doble propósito, servido como
sitio estático en **GitHub Pages** (Tailwind CSS + Alpine.js, paleta
miel). Ver [`CONTEXTO.md`](CONTEXTO.md) para la estructura completa, el
enrutamiento y las reglas de diseño.

- `index.html` — selección de usuario + interfaz
- `interfaz1.html` — terreno 3D + vista satelital con simulador de crecida
- `interfaz2.html` / `interfaz3.html` — placeholders (datos/precios y
  bitácora de colmenas)
- `interfaz4.html` — contexto meteorológico de visitas: registrar visitas y
  ver los informes que el motor ([`interfaz4/`](interfaz4/README.md), Python
  en GitHub Actions) envía por correo 24 h y 12 h antes
- `bitacoraderevision/` — **Interfaz 5**: bitácora de revisión de colmenas con registros,
  nueva revisión (incluye varroa y acaricida) y el **mapa del apiario**; sitio
  autocontenido con su propio backend en Google Sheets
  (<https://eduabejas.github.io/apiario-portal/bitacoraderevision/>, ver
  [su README](bitacoraderevision/README.md))
- `assets/` — CSS compilado, Alpine.js, datos y media

**Deploy:** cada push a `main` que toque `index.html`, `interfaz*.html`,
`assets/**` o `bitacoraderevision/**` corre `.github/workflows/pages.yml` y publica en GitHub
Pages (<https://eduabejas.github.io/apiario-portal/>). Para regenerar el CSS tras tocar clases: `npm install && npm run
build:css`.

**Origen Apps Script:** el código de la versión anterior (Google Apps
Script) sigue en [`colmena-portal/`](colmena-portal/) — ver ese README.
Su propio deploy (`clasp push` + `clasp deploy` vía
`.github/workflows/deploy.yml`) sigue activo por si Interfaz 2/3
necesitan un endpoint JSON contra `Apiario_DB` más adelante.
