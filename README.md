# apiario-portal

Portal único para el proyecto de apiario doble propósito, servido como
sitio estático en **GitHub Pages** (Tailwind CSS + Alpine.js, paleta
miel). Ver [`CONTEXTO.md`](CONTEXTO.md) para la estructura completa, el
enrutamiento y las reglas de diseño.

- `index.html` — selección de usuario + interfaz
- `interfaz1.html` — terreno 3D + vista satelital con simulador de crecida
- `interfaz2.html` — placeholder (datos y precios)
- `interfaz3.html` — **Interfaz 3**: registrar revisiones desde el celular
  (todos los campos de la bitácora, QR en las tapas, funciona sin señal);
  escribe en la misma hoja que la Interfaz 5
- `interfaz4.html` — contexto meteorológico de visitas: registrar visitas y
  ver los informes que el motor ([`interfaz4/`](interfaz4/README.md), Python
  en GitHub Actions) envía por correo 24 h y 12 h antes
- `bitacoraderevision/` — **Interfaz 5**: registros de revisiones y el **mapa
  del apiario**; trae el backend de la bitácora (Google Sheets + Apps Script,
  compartido con la Interfaz 3; la URL va en `bitacoraderevision/assets/config.js`)
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
