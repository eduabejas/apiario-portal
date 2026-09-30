# apiario-portal

Portal único (Google Apps Script) para el proyecto de apiario doble propósito.
El código vive en [`colmena-portal/`](colmena-portal/) — ver ese README para
estructura, puesta en marcha y el flujo de despliegue automático vía GitHub
Actions + clasp.

**Deploy:** cada push a `main` que toque `colmena-portal/**` corre
`.github/workflows/deploy.yml`, que hace `clasp push` + `clasp deploy` y
actualiza la misma URL `/exec`, sin tocar terminal.
