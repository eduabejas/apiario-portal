/**
 * Portal semilla — Apiario doble propósito
 * Enrutador único: una sola URL /exec que decide qué vista servir.
 *   /exec                 → Portal (usuario + interfaz)
 *   /exec?u=rocio&i=1     → Interfaz 1 (Satélites / QGIS soft)
 *   /exec?u=rocio&i=2     → Interfaz 2 (Datos / Excel)
 *   /exec?u=rocio&i=3     → Interfaz 3 (Bitácora de colmenas)
 * Sin contraseñas en esta primera vuelta.
 */

const USUARIOS = {
  rocio:   { nombre: 'Rocío Barni',     rol: 'Administrador', iniciales: 'RB' },
  eduardo: { nombre: 'Eduardo Mendoza', rol: 'Administrador', iniciales: 'EM' }
};

const INTERFACES = {
  '1': { vista: 'Interfaz1', titulo: 'Satélites, precipitaciones y QGIS soft', icono: '🛰️' },
  '2': { vista: 'Interfaz2', titulo: 'Datos, precios y gráficos', icono: '📊' },
  '3': { vista: 'Interfaz3', titulo: 'Bitácora de colmenas', icono: '📋' }
};

function doGet(e) {
  const p = (e && e.parameter) || {};
  const u = String(p.u || '').toLowerCase();
  const i = String(p.i || '');

  const usuario = USUARIOS[u];
  const iface = INTERFACES[i];

  // Sin usuario o interfaz válidos → portal
  if (!usuario || !iface) return render_('Portal', { usuarios: USUARIOS, interfaces: INTERFACES }, 'Portal Apiario');

  registrarAcceso_(u, i);
  return render_(iface.vista, { usuario: usuario, userKey: u, iface: iface }, iface.titulo);
}

function render_(vista, datos, titulo) {
  const t = HtmlService.createTemplateFromFile(vista);
  t.baseUrl = ScriptApp.getService().getUrl();
  Object.keys(datos).forEach(k => t[k] = datos[k]);
  return t.evaluate()
    .setTitle(titulo)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL);
}

/** Permite <?!= include('Estilos') ?> dentro de las vistas */
function include(nombre) {
  return HtmlService.createHtmlOutputFromFile(nombre).getContent();
}

/**
 * Registro mínimo de accesos en una Google Sheet que se crea sola
 * la primera vez (queda en el Drive de edumendozaagro@gmail.com).
 * Es también la futura "base de datos" de la Interfaz 3.
 */
function registrarAcceso_(u, i) {
  try {
    const hoja = db_().getSheetByName('Accesos') || db_().insertSheet('Accesos');
    if (hoja.getLastRow() === 0) hoja.appendRow(['Fecha', 'Usuario', 'Interfaz']);
    hoja.appendRow([new Date(), u, i]);
  } catch (err) {
    console.warn('No se pudo registrar acceso: ' + err);
  }
}

function db_() {
  const props = PropertiesService.getScriptProperties();
  let id = props.getProperty('DB_ID');
  if (id) return SpreadsheetApp.openById(id);
  const ss = SpreadsheetApp.create('Apiario_DB');
  props.setProperty('DB_ID', ss.getId());
  return ss;
}
