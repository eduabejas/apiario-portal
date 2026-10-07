# Bitácora de revisión de colmenas

Sitio web para registrar las revisiones (aperturas) de cada colmena del apiario
**Predio 6 Agosto — Apis Agroecológica**.

- **Lectura pública:** cualquiera puede consultar las revisiones.
- **Escritura protegida:** solo quien conoce el **código de acceso** puede registrar.
  El código se valida **en el servidor** (no en el navegador), así que es seguridad real.

Todo es **gratuito**: GitHub Pages para el sitio y Google Sheets como base de datos.
No hace falta tarjeta ni pagar ningún servicio.

## Arquitectura

```
Apicultor (navegador) -> GitHub Pages (sitio, HTTPS) -> Google Apps Script -> Hoja de Google
```

- **Frontend:** HTML + CSS + JavaScript, servido por GitHub Pages.
- **Backend:** una Hoja de cálculo de Google + un script (Apps Script) que lee y
  escribe en ella. La lectura es pública; la escritura pide el código de acceso.

```
.
├── index.html            # Página principal (lista + formulario)
├── assets/
│   ├── styles.css        # Estilos (claro/oscuro, mobile-first)
│   ├── app.js            # Lógica: leer, filtrar y registrar revisiones
│   └── config.js         # URL de la app web de Google (pegás tu valor)
├── apps-script/
│   └── Codigo.gs         # Script para pegar en Google Apps Script
└── .nojekyll
```

## Puesta en marcha (una sola vez, ~10 minutos)

### 1. Crear la hoja y el script
1. Entrá a [sheets.new](https://sheets.new) para crear una Hoja de cálculo de Google
   (con tu cuenta de Google). Ponele un nombre, ej. *Bitácora de colmenas*.
2. En el menú: **Extensiones → Apps Script**. Se abre el editor.
3. Borrá el código de ejemplo, abrí [`apps-script/Codigo.gs`](apps-script/Codigo.gs),
   copiá **todo** su contenido y pegalo. Guardá (ícono del disquete).

### 2. Fijar el código de acceso
1. En el editor de Apps Script, en la función `configurarCodigo()`, cambiá
   `CAMBIA-ESTE-CODIGO` por tu código real (recomendado: 8+ caracteres con letras y
   números, ej. `Colmena6Agosto2026`).
2. Arriba, elegí la función **`configurarCodigo`** en el desplegable y presioná
   **Ejecutar** ▶. La primera vez te pedirá **autorizar** los permisos (es normal:
   es tu propio script sobre tu propia hoja) → Aceptá.
   > El código queda guardado en el servidor de Google, **no** en el sitio ni en
   > GitHub. Después de ejecutarlo podés volver a poner un texto cualquiera en esa
   > línea si vas a compartir el script.

### 3. Publicar la app web
1. Arriba a la derecha: **Implementar → Nueva implementación**.
2. En el engranaje ⚙ elegí **Aplicación web**.
3. Configurá:
   - **Ejecutar como:** Yo (tu cuenta)
   - **Quién tiene acceso:** **Cualquier persona**
4. **Implementar** → autorizá si lo pide → copiá la **URL de la aplicación web**
   (termina en `/exec`).

### 4. Conectar el sitio
1. Pegá esa URL en [`assets/config.js`](assets/config.js):
   ```js
   window.APP_CONFIG = {
     WEBAPP_URL: "https://script.google.com/macros/s/XXXXXXXX/exec"
   };
   ```
2. Guardá el cambio (commit) en GitHub.

### 5. Activar GitHub Pages
1. En GitHub → el repo → **Settings** → **Pages**.
2. **Source:** **Deploy from a branch** → **Branch:** `main` / carpeta `/ (root)` → **Save**.
3. En un minuto el sitio queda publicado en:
   `https://apisagroecologicapredio6agosto.github.io/bitacoraderevision/`

## Cambiar el código de acceso más adelante
En el editor de Apps Script, cambiá el valor en `configurarCodigo()` y ejecutá la
función otra vez. (No hace falta volver a implementar.)

## Actualizar el script si cambia `Codigo.gs`
Si más adelante mejoramos el script: pegá la nueva versión en el editor y hacé
**Implementar → Gestionar implementaciones → editar (lápiz) → Versión: Nueva → Implementar**.
Así la URL sigue siendo la misma.

## Notas de seguridad
- Todo el tráfico va por **HTTPS**.
- La URL de la app web puede ir en el sitio: por sí sola no permite escribir; hace
  falta el **código de acceso**, que se verifica en el servidor.
- El código **no** se guarda en el sitio ni en el repositorio.
- Los datos quedan en **tu** Hoja de Google, que podés ver, respaldar y exportar
  cuando quieras.
- Recomendación: usá un código largo. Para trazabilidad por persona (saber quién
  registró cada revisión) se puede agregar login más adelante.

## Ideas para mejorar más adelante
- Editar / borrar registros (con el código).
- Gráficos de evolución por colmena (postura, reservas, sanidad en el tiempo).
- Fichas por colmena con su historial completo.
- Exportar a Excel/PDF desde el sitio.
- Fotos por revisión.

---
Proyecto de **Apis Agroecológica · Predio 6 Agosto**.
