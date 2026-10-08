# Bitácora de revisión de colmenas

Bitácora de revisiones (aperturas) de cada colmena y mapa del apiario, en dos
interfaces del [Portal Apiario](https://eduabejas.github.io/apiario-portal/) que
comparten la misma hoja de Google:

- **Interfaz 3 — Registrar revisión** ([`interfaz3.html`](../interfaz3.html)):
  pensada para el celular en el campo. Botones grandes con todos los campos de
  la revisión, QR en las tapas, funciona sin señal (guarda en el teléfono y
  envía sola cuando vuelve la conexión) y muestra la última revisión de cada
  colmena.
- **Interfaz 5 — Registros y mapa** (esta carpeta): lista de revisiones con
  buscador y el mapa del apiario con el estado sanitario de cada colmena.

- **Lectura pública:** cualquiera puede consultar las revisiones.
- **Escritura protegida:** solo quien conoce el **código de acceso** puede registrar.
  El código se valida **en el servidor** (no en el navegador), así que es seguridad real.

Todo es **gratuito**: GitHub Pages para el sitio y Google Sheets como base de datos.
No hace falta tarjeta ni pagar ningún servicio.

Vive en la carpeta `bitacoraderevision/` del repo
[`eduabejas/apiario-portal`](https://github.com/eduabejas/apiario-portal) y se
publica en <https://eduabejas.github.io/apiario-portal/bitacoraderevision/>. Se
entra desde el portal eligiendo usuario e **Interfaz 5**, y el enlace «← Portal»
de la cabecera vuelve al inicio.

## Arquitectura

```
Celular (Interfaz 3) ─┐
                      ├─> GitHub Pages (sitio, HTTPS) -> Google Apps Script -> Hoja de Google
Registros/mapa (I. 5) ┘
```

- **Frontend:** HTML + CSS + JavaScript, servido por GitHub Pages.
- **Backend:** una Hoja de cálculo de Google + un script (Apps Script) que lee y
  escribe en ella. La lectura es pública; la escritura pide el código de acceso.

```
bitacoraderevision/
├── index.html            # Interfaz 5: registros y mapa
├── assets/
│   ├── styles.css        # Estilos (claro/oscuro, mobile-first)
│   ├── app.js            # Lógica: leer y filtrar revisiones; pestañas
│   ├── mapa.css          # Estilos del mapa del apiario
│   ├── mapa.js           # Mapa del apiario (SVG, sin librerías)
│   └── config.js         # URL de la app web de Google (la usan la Interfaz 3 y la 5)
└── apps-script/
    └── Codigo.gs         # Script para pegar en Google Apps Script (no se publica)
```

Cada pestaña tiene su propio enlace: `…/#registros` y `…/#mapa`. El botón
**＋ Registrar revisión** (y cualquier enlace viejo a `…/#nueva`) lleva a la
Interfaz 3. El formulario de la Interfaz 3 está en `../interfaz3.html` y
`../assets/js/bitacora*.js` (ver el README del portal).

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
   números, ej. `ColmenaMiel2026`).
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
2. Guardá el cambio (commit) en `main`. La Interfaz 3 toma la URL de este
   mismo archivo: no hay que pegarla en otro lado.

### 5. Publicación
No hay que configurar nada más: cada push a `main` que toque
`bitacoraderevision/**` corre `.github/workflows/pages.yml` del repo, que
publica la carpeta (sin `apps-script/`) junto con el portal. En un minuto queda en
<https://eduabejas.github.io/apiario-portal/bitacoraderevision/>.

## Cambiar el código de acceso más adelante
En el editor de Apps Script, cambiá el valor en `configurarCodigo()` y ejecutá la
función otra vez. (No hace falta volver a implementar.)

## Actualizar el script si cambia `Codigo.gs`
Si más adelante mejoramos el script: pegá la nueva versión en el editor y hacé
**Implementar → Gestionar implementaciones → editar (lápiz) → Versión: Nueva → Implementar**.
Así la URL sigue siendo la misma.

> **Importante para el mapa:** la pestaña «Mapa» y los campos de varroa
> necesitan la versión de `Codigo.gs` que los incluye. Si ya tenías implementada
> una versión anterior del script, hasta que la actualices el sitio sigue
> registrando y mostrando revisiones como antes y el mapa muestra «Falta
> actualizar el script de Google para usar el mapa». Al implementarla, el script
> agrega solo las columnas nuevas de la hoja `revisiones` (`varroa_pct`,
> `acaricida`, al final) y crea la hoja `mapa`.
>
> **Envíos sin señal (Interfaz 3):** el celular manda cada revisión con su
> propio id, y la versión actual del script descarta un reintento que ya había
> llegado (por ejemplo, si se cortó la señal justo antes de la respuesta). Con
> un script anterior todo funciona igual, pero en ese caso raro la revisión
> podría quedar dos veces.

## Mapa del apiario
La pestaña **Mapa** es un plano en vista superior (el Norte siempre arriba)
donde se dibuja la disposición del apiario. Empieza vacío.

**Ver** (cualquiera):
- Arrastrá para moverte, usá la rueda o pellizcá para acercar/alejar, y ⤢ (o
  la tecla `0`) para encuadrar todo.
- Al pasar el mouse por una colmena o un núcleo (o tocarlo en el celular) se
  ve: código, alias, edad de la reina, última aplicación de acaricida y último
  análisis de varroa. Si el último varroa es **≥ 3,0 %**, el valor aparece en
  rojo y la colmena tiene contorno y punto rojos.
- Los datos sanitarios salen de las revisiones: el **N.º de colmena** de la
  revisión tiene que coincidir con el **código** del mapa. La Interfaz 3 muestra
  las colmenas del mapa como botones (con ✓ las ya revisadas hoy) y las sugiere
  al escribir. Su sección «Sanidad (varroa)» tiene el porcentaje de varroa y el
  acaricida aplicado.

**Editar** (quien tenga el código de acceso):
1. Tocá **Editar** y usá **+** para agregar colmenas, núcleos, pallets, muros,
   vallas o etiquetas. Aparecen en el centro de la vista.
2. Arrastrá para mover; usá las asas de las esquinas para cambiar el tamaño y
   el asa redonda para rotar (de a 15°). Todo se ajusta a una grilla de 5 cm;
   mantené **Alt** para moverlo libre. Los extremos de muros y vallas se pegan
   entre sí para cerrar perímetros.
3. En el panel de propiedades se editan código, alias, fecha de la reina,
   notas y medidas. Se puede **Duplicar** o **Eliminar**. Teclado: flechas
   (5 cm), Shift + flechas (50 cm), Supr, Ctrl/Cmd + D, Ctrl/Cmd + Z y
   Ctrl/Cmd + Shift + Z.
4. **Guardar** pide el código de acceso (una vez por sesión). Queda anotado
   como guardado por el usuario elegido en el portal. Si otra persona
   guardó antes, se puede **Sobrescribir** o **Descartar mis cambios**.
   Mientras se edita, el navegador guarda un borrador por si se cierra la
   página; al volver a Editar se ofrece recuperarlo.

Cada guardado agrega una fila en la hoja `mapa` (con versión, fecha y quién
guardó), así queda el historial completo del plano.

## Notas de seguridad
- Todo el tráfico va por **HTTPS**.
- La URL de la app web puede ir en el sitio: por sí sola no permite escribir; hace
  falta el **código de acceso**, que se verifica en el servidor.
- El código **no** se guarda en el sitio ni en el repositorio.
- Los datos quedan en **tu** Hoja de Google, que podés ver, respaldar y exportar
  cuando quieras.
- El código que se ingresa en el mapa queda solo en la memoria de la página
  (nunca en el almacenamiento del navegador ni en la URL). El borrador local del
  mapa no incluye el código.
- En la Interfaz 3 el código queda en memoria mientras la página está abierta
  (así las revisiones guardadas sin señal se envían solas). Solo se guarda en el
  celular si se tilda **«Recordar en este celular»**; si el servidor lo rechaza,
  se borra y se vuelve a pedir. Nunca viaja en la URL ni se guarda junto con las
  revisiones pendientes.
- Recomendación: usá un código largo. Para trazabilidad por persona (saber quién
  registró cada revisión) se puede agregar login más adelante.

## Ideas para mejorar más adelante
- Editar / borrar registros (con el código).
- Gráficos de evolución por colmena (postura, reservas, sanidad en el tiempo).
- Fichas por colmena con su historial completo.
- Exportar a Excel/PDF desde el sitio.
- Fotos por revisión.

---
Parte del [Portal Apiario](https://eduabejas.github.io/apiario-portal/).
