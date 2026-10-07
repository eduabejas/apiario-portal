/**
 * ============================================================================
 *  Bitácora de revisión de colmenas — Backend con Google Sheets
 *  Apis Agroecológica · Predio 6 Agosto
 * ----------------------------------------------------------------------------
 *  Este script convierte una Hoja de cálculo de Google en el backend del sitio.
 *
 *    • LECTURA  pública   -> doGet devuelve todos los registros en JSON.
 *    • ESCRITURA protegida -> doPost exige un CÓDIGO DE ACCESO que se valida
 *      aquí, en el servidor. El código se guarda en las "Propiedades del script"
 *      (Script Properties), NUNCA en el sitio ni en GitHub.
 *
 *  Puesta en marcha (ver README para el detalle):
 *    1. Crear una Hoja de cálculo de Google.
 *    2. Extensiones -> Apps Script. Borrar lo que haya y pegar TODO este archivo.
 *    3. Editar la línea del código en configurarCodigo() y ejecutar esa función
 *       UNA vez (o cargar la propiedad CODIGO_ACCESO a mano en Configuración).
 *    4. Implementar -> Nueva implementación -> Aplicación web:
 *         - Ejecutar como: Yo
 *         - Quién tiene acceso: Cualquier persona
 *       Copiar la URL de la app web y pegarla en assets/config.js.
 * ============================================================================
 */

var NOMBRE_HOJA = 'revisiones';
var COLUMNAS = [
  'id', 'creado_en', 'fecha', 'numero_colmena', 'apiario', 'postura',
  'estado_reina', 'cria_operculada', 'reservas_miel', 'reservas_polen',
  'reina_vista', 'huevos', 'poblacion', 'temperamento', 'sanidad',
  'celdas_reales', 'acciones', 'observaciones', 'registrado_por'
];

/**
 * Configura el código de acceso. EDITÁ el valor y ejecutá esta función UNA vez.
 * (Alternativa: Apps Script -> Configuración del proyecto -> Propiedades del
 *  script -> agregar propiedad  CODIGO_ACCESO  con tu código.)
 * No dejes tu código real escrito acá si vas a compartir el script.
 */
function configurarCodigo() {
  PropertiesService.getScriptProperties()
    .setProperty('CODIGO_ACCESO', 'CAMBIA-ESTE-CODIGO');
}

/** Devuelve (creando si hace falta) la hoja de registros con sus encabezados. */
function obtenerHoja_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(NOMBRE_HOJA);
  if (!sh) {
    sh = ss.insertSheet(NOMBRE_HOJA);
  }
  if (sh.getLastRow() === 0) {
    sh.appendRow(COLUMNAS);
    sh.getRange(1, 1, 1, COLUMNAS.length).setFontWeight('bold');
    sh.setFrozenRows(1);
    // Guardar fecha y número de colmena como texto (evita conversiones raras).
    sh.getRange('C:C').setNumberFormat('@'); // fecha
    sh.getRange('D:D').setNumberFormat('@'); // numero_colmena
  }
  return sh;
}

/** LECTURA pública: devuelve todos los registros, del más nuevo al más viejo. */
function doGet() {
  try {
    var sh = obtenerHoja_();
    var valores = sh.getDataRange().getValues();
    var encabezado = valores.shift() || COLUMNAS;
    var tz = Session.getScriptTimeZone();
    var filas = valores.map(function (r) {
      var o = {};
      for (var i = 0; i < encabezado.length; i++) {
        var h = encabezado[i];
        var v = r[i];
        if (Object.prototype.toString.call(v) === '[object Date]') {
          v = (h === 'fecha')
            ? Utilities.formatDate(v, tz, 'yyyy-MM-dd')
            : v.toISOString();
        }
        o[h] = v;
      }
      o.acciones = (typeof o.acciones === 'string' && o.acciones)
        ? o.acciones.split('|')
        : [];
      return o;
    });
    filas.reverse();
    return json_({ ok: true, data: filas });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

/** ESCRITURA protegida: valida el código y agrega la revisión. */
function doPost(e) {
  try {
    var cuerpo = JSON.parse((e && e.postData && e.postData.contents) || '{}');
    var codigo = cuerpo.codigo || '';
    var esperado = PropertiesService.getScriptProperties().getProperty('CODIGO_ACCESO');

    if (!esperado) {
      return json_({ ok: false, error: 'El código no está configurado en el servidor.' });
    }
    if (codigo !== esperado) {
      return json_({ ok: false, error: 'Código de acceso inválido.' });
    }

    var d = cuerpo.datos || {};
    if (!d.numero_colmena || !d.fecha) {
      return json_({ ok: false, error: 'Faltan datos obligatorios (colmena y fecha).' });
    }

    var sh = obtenerHoja_();
    var id = Utilities.getUuid();
    var creado = new Date().toISOString();
    var acciones = Array.isArray(d.acciones) ? d.acciones.join('|') : '';

    sh.appendRow([
      id, creado, String(d.fecha), String(d.numero_colmena), d.apiario || '',
      d.postura || '', d.estado_reina || '', d.cria_operculada || '',
      d.reservas_miel || '', d.reservas_polen || '', d.reina_vista || '',
      d.huevos || '', d.poblacion || '', d.temperamento || '', d.sanidad || '',
      d.celdas_reales || '', acciones, d.observaciones || '', d.registrado_por || ''
    ]);

    return json_({ ok: true, id: id });
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

/** Respuesta JSON. */
function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
