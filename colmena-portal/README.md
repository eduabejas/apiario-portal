# 🐝 Portal Apiario — semilla

Una sola URL de Google Apps Script que pregunta **usuario** e **interfaz** y enruta a:

| # | Interfaz | Estado |
|---|----------|--------|
| 1 | Satélites, precipitaciones, QGIS soft (mapas 2D/3D, inundación, viento) | placeholder |
| 2 | Datos, precios, fórmulas, gráficos (Sheets) | placeholder |
| 3 | Bitácora de revisión de colmenas | placeholder |

Usuarios: Rocío Barni, Eduardo Mendoza (Administradores). Sin contraseñas en esta vuelta.

## Estructura

```
colmena-portal/
├── .clasp.json                 # scriptId + rootDir
├── .github/workflows/deploy.yml# push a main → clasp push + redeploy
└── src/
    ├── appsscript.json         # manifiesto: webapp pública, V8
    ├── Code.gs                 # doGet enrutador, usuarios, log en Sheet
    ├── Estilos.html            # CSS compartido (paleta miel)
    ├── Portal.html             # selección usuario + interfaz
    ├── Interfaz1.html
    ├── Interfaz2.html
    └── Interfaz3.html
```

Rutas: `/exec` → portal · `/exec?u=rocio&i=3` → Interfaz 3 directa (sirve como marcador).

Al primer acceso a una interfaz se crea sola la hoja **Apiario_DB** en tu Drive, con la pestaña `Accesos`. Esa misma hoja será la base de la bitácora.

---

## Puesta en marcha (una vez, ~15 min)

### A. URL funcionando (solo navegador)
1. Entra a <https://script.google.com> con `edumendozaagro@gmail.com` → **Nuevo proyecto**. Nómbralo `Portal Apiario`.
2. ⚙️ Configuración del proyecto → activa **"Mostrar archivo de manifiesto appsscript.json"**.
3. Copia el contenido de cada archivo de `src/` (crea los `.html` con **+ → HTML**, sin la extensión en el nombre).
4. **Implementar → Nueva implementación → Aplicación web**
   - Ejecutar como: **Yo**
   - Quién tiene acceso: **Cualquier usuario**
5. Autoriza (Drive/Sheets, por el log) y copia la URL `/exec`. ✅ Ya es la URL común.

Anota dos IDs:
- **Script ID**: Configuración del proyecto → IDs.
- **Deployment ID**: Implementar → Gestionar implementaciones → ID (empieza con `AKfy…`).

### B. GitHub como fuente de verdad
1. Crea el repo (ej. `apiario-portal`) y sube esta carpeta. Pega el Script ID en `.clasp.json`.
2. En tu PC, una vez:
   ```bash
   npm i -g @google/clasp
   clasp login          # abre Google, crea ~/.clasprc.json
   ```
   Activa también la API en <https://script.google.com/home/usersettings>.
3. En GitHub → Settings → Secrets and variables → Actions, crea:
   - `CLASPRC_JSON` = contenido completo de `~/.clasprc.json`
   - `DEPLOYMENT_ID` = el `AKfy…` del paso A
4. Cada `git push` a `main` sube el código y actualiza **la misma URL**.

> Nota: `CLASPRC_JSON` da acceso a los scripts de tu cuenta; úsalo solo en repos privados.

---

## Siguientes pasos sugeridos
1. **Interfaz 3**: formulario de revisión → `google.script.run.guardarRevision(obj)` → hoja `Revisiones`.
2. **Interfaz 2**: leer/graficar hojas de Apiario_DB (Chart.js vía CDN).
3. **Interfaz 1**: Leaflet (2D) + MapLibre con terreno (3D), precipitación desde Open-Meteo, inundación = umbral sobre DEM.
