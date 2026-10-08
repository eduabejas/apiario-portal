/**
 * ============================================================================
 *  Bitácora de revisión de colmenas — Backend con Google Sheets
 *  Portal Apiario
 * ----------------------------------------------------------------------------
 *  Este script convierte una Hoja de cálculo de Google en el backend del sitio.
 *
 *    • LECTURA  pública   -> doGet devuelve los registros (o el mapa) en JSON.
 *        GET                    -> revisiones   { ok, data }
 *        GET ?recurso=mapa      -> mapa vigente { ok, version, guardado_en, data }
 *    • ESCRITURA protegida -> doPost exige un CÓDIGO DE ACCESO que se valida
 *      aquí, en el servidor. El código se guarda en las "Propiedades del script"
 *      (Script Properties), NUNCA en el sitio ni en GitHub.
 *        POST { codigo, datos }                        -> registra una revisión
 *          (datos.id_cliente opcional: un reintento con el mismo id no duplica)
 *        POST { accion: 'guardar_mapa', codigo, ... }  -> guarda una versión del mapa
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
 *  Si ya estaba implementado y cambió este archivo: Implementar -> Gestionar
 *  implementaciones -> editar (lápiz) -> Versión: Nueva -> Implementar.
 * ============================================================================
 */

var NOMBRE_HOJA = 'revisiones';
// Columnas nuevas SIEMPRE al final: obtenerHoja_() migra hojas viejas
// agregando los encabezados que falten, sin reordenar los existentes.
var COLUMNAS = [
  'id', 'creado_en', 'fecha', 'numero_colmena', 'apiario', 'postura',
  'estado_reina', 'cria_operculada', 'reservas_miel', 'reservas_polen',
  'reina_vista', 'huevos', 'poblacion', 'temperamento', 'sanidad',
  'celdas_reales', 'acciones', 'observaciones', 'registrado_por',
  'varroa_pct', 'acaricida'
];

var NOMBRE_HOJA_MAPA = 'mapa';
// Una celda de Google Sheets admite hasta 50.000 caracteres, pero el mapa puede
// llegar a 200.000: el JSON se reparte en trozos en las columnas json, json_2…
var COLUMNAS_MAPA = ['version', 'guardado_en', 'guardado_por', 'json', 'json_2', 'json_3', 'json_4', 'json_5'];
var TROZO_JSON = 45000;

var TIPOS_MAPA = ['colmena', 'nucleo', 'pallet', 'muro', 'valla', 'etiqueta'];
var MAX_ITEMS_MAPA = 500;
var MAX_JSON_MAPA = 200000;
var LIMITE_COORD = 1000;

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

/* ============================================================================
 *  Enrutamiento
 * ========================================================================== */

function doGet(e) {
  var recurso = (e && e.parameter && e.parameter.recurso) || 'revisiones';
  if (recurso === 'mapa') return json_(leerMapa_());
  return json_(leerRevisiones_());
}

function doPost(e) {
  try {
    var cuerpo = parsear_(e);
    var accion = cuerpo.accion || 'registrar_revision';

    var esperado = PropertiesService.getScriptProperties().getProperty('CODIGO_ACCESO');
    if (!esperado) {
      return json_({ ok: false, error: 'El código no está configurado en el servidor.' });
    }
    if (!codigoValido_(cuerpo.codigo)) {
      return json_({ ok: false, error: 'Código de acceso inválido.' });
    }

    var lock = LockService.getScriptLock();
    lock.waitLock(10000);
    try {
      if (accion === 'guardar_mapa') return json_(guardarMapa_(cuerpo));
      if (accion === 'registrar_revision') return json_(registrarRevision_(cuerpo));
      return json_({ ok: false, error: 'Acción desconocida.' });
    } finally {
      lock.releaseLock();
    }
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function parsear_(e) {
  return JSON.parse((e && e.postData && e.postData.contents) || '{}');
}

function codigoValido_(codigo) {
  var esperado = PropertiesService.getScriptProperties().getProperty('CODIGO_ACCESO');
  return !!esperado && String(codigo || '') === esperado;
}

/* ============================================================================
 *  Revisiones
 * ========================================================================== */

/** Devuelve (creando o migrando si hace falta) la hoja de registros. */
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
    return sh;
  }

  // Migración: hojas creadas con una versión anterior tienen menos encabezados.
  var encabezado = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
  var n = encabezado.length;
  while (n > 0 && encabezado[n - 1] === '') n--;
  if (n < COLUMNAS.length) {
    if (sh.getMaxColumns() < COLUMNAS.length) {
      sh.insertColumnsAfter(sh.getMaxColumns(), COLUMNAS.length - sh.getMaxColumns());
    }
    var faltan = COLUMNAS.slice(n);
    sh.getRange(1, n + 1, 1, faltan.length).setValues([faltan]).setFontWeight('bold');
  }
  return sh;
}

/** LECTURA pública: devuelve todos los registros, del más nuevo al más viejo. */
function leerRevisiones_() {
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
    return { ok: true, data: filas };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/** ESCRITURA (código ya validado en doPost): agrega una revisión. */
function registrarRevision_(cuerpo) {
  var d = cuerpo.datos || {};
  if (!d.numero_colmena || !d.fecha) {
    return { ok: false, error: 'Faltan datos obligatorios (colmena y fecha).' };
  }

  var varroa = varroaPct_(d.varroa_pct);
  if (varroa.error) return { ok: false, error: varroa.error };
  var acaricida = String(d.acaricida == null ? '' : d.acaricida).trim().slice(0, 60);

  var sh = obtenerHoja_();
  // La Interfaz 3 manda su propio id (id_cliente) y reintenta sin señal: si
  // ese id ya está en la hoja, el envío anterior había llegado.
  var idCliente = String(d.id_cliente || '');
  var conIdCliente = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(idCliente);
  if (conIdCliente && existeId_(sh, idCliente)) return { ok: true, id: idCliente, duplicado: true };
  var id = conIdCliente ? idCliente : Utilities.getUuid();
  var creado = new Date().toISOString();
  var acciones = Array.isArray(d.acciones) ? d.acciones.join('|') : '';

  sh.appendRow([
    id, creado, String(d.fecha), String(d.numero_colmena), d.apiario || '',
    d.postura || '', d.estado_reina || '', d.cria_operculada || '',
    d.reservas_miel || '', d.reservas_polen || '', d.reina_vista || '',
    d.huevos || '', d.poblacion || '', d.temperamento || '', d.sanidad || '',
    d.celdas_reales || '', acciones, d.observaciones || '', d.registrado_por || '',
    varroa.valor, acaricida
  ]);

  return { ok: true, id: id };
}

/** ¿Hay una revisión con ese id (columna A)? */
function existeId_(sh, id) {
  var n = sh.getLastRow() - 1;
  if (n < 1) return false;
  var ids = sh.getRange(2, 1, n, 1).getValues();
  for (var i = 0; i < ids.length; i++) if (String(ids[i][0]) === id) return true;
  return false;
}

/** '' (sin análisis) o un número 0–100 redondeado a 1 decimal. */
function varroaPct_(v) {
  if (v == null) return { valor: '' };
  var texto = String(v).trim();
  if (texto === '') return { valor: '' };
  var n = Number(texto.replace(',', '.'));
  if (!isFinite(n) || n < 0 || n > 100) {
    return { error: 'El análisis de varroa debe ser un número entre 0 y 100.' };
  }
  return { valor: Math.round(n * 10) / 10 };
}

/* ============================================================================
 *  Mapa del apiario
 * ========================================================================== */

function obtenerHojaMapa_() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sh = ss.getSheetByName(NOMBRE_HOJA_MAPA);
  if (!sh) {
    sh = ss.insertSheet(NOMBRE_HOJA_MAPA);
  }
  if (sh.getLastRow() === 0) {
    // Texto plano en todo lo que no es la versión: el JSON (y el nombre de quien
    // guarda) nunca debe interpretarse como número, fecha ni fórmula.
    sh.getRange('B:H').setNumberFormat('@');
    sh.appendRow(COLUMNAS_MAPA);
    sh.getRange(1, 1, 1, COLUMNAS_MAPA.length).setFontWeight('bold');
    sh.setFrozenRows(1);
  }
  return sh;
}

function mapaVacio_() {
  return { esquema: 1, unidad: 'm', items: [] };
}

/** Última fila de la hoja mapa (la versión vigente), o null si no hay. */
function ultimaVersionMapa_(sh) {
  var ultima = sh.getLastRow();
  if (ultima < 2) return null;
  var fila = sh.getRange(ultima, 1, 1, COLUMNAS_MAPA.length).getValues()[0];
  var guardadoEn = fila[1];
  if (Object.prototype.toString.call(guardadoEn) === '[object Date]') guardadoEn = guardadoEn.toISOString();
  return {
    version: Number(fila[0]) || 0,
    guardado_en: guardadoEn ? String(guardadoEn) : null,
    json: fila.slice(3).join('')
  };
}

/** LECTURA pública del mapa vigente. */
function leerMapa_() {
  try {
    var vigente = ultimaVersionMapa_(obtenerHojaMapa_());
    if (!vigente) return { ok: true, version: 0, guardado_en: null, data: mapaVacio_() };
    var data;
    try {
      data = JSON.parse(vigente.json);
    } catch (errJson) {
      return { ok: false, error: 'El mapa guardado está dañado (revisar la hoja "mapa").' };
    }
    return { ok: true, version: vigente.version, guardado_en: vigente.guardado_en, data: data };
  } catch (err) {
    return { ok: false, error: String(err) };
  }
}

/**
 * ESCRITURA (código ya validado en doPost):
 * cuerpo = { accion, codigo, base_version, guardado_por, mapa }.
 * Cada guardado agrega una fila nueva (historial); la vigente es la última.
 */
function guardarMapa_(cuerpo) {
  var sh = obtenerHojaMapa_();
  var vigente = ultimaVersionMapa_(sh);
  var versionActual = vigente ? vigente.version : 0;

  if (Number(cuerpo.base_version) !== versionActual) {
    return { ok: false, error: 'conflicto', version: versionActual };
  }

  var resultado = validarMapa_(cuerpo.mapa);
  if (resultado.error) return { ok: false, error: resultado.error };

  var texto = JSON.stringify(resultado.mapa);
  var trozos = [];
  for (var i = 0; i < COLUMNAS_MAPA.length - 3; i++) {
    trozos.push(texto.slice(i * TROZO_JSON, (i + 1) * TROZO_JSON));
  }

  var nueva = versionActual + 1;
  var guardadoPor = String(cuerpo.guardado_por == null ? '' : cuerpo.guardado_por).trim().slice(0, 80);
  sh.appendRow([nueva, new Date().toISOString(), guardadoPor].concat(trozos));
  return { ok: true, version: nueva };
}

/**
 * Valida el documento completo y devuelve { mapa: limpio } o { error }.
 * Mismas reglas que validarMapa() en assets/mapa.js. Descarta campos desconocidos.
 */
function validarMapa_(mapa) {
  if (!mapa || typeof mapa !== 'object' || Array.isArray(mapa)) {
    return { error: 'El mapa no tiene un formato válido.' };
  }
  if (mapa.esquema !== 1) return { error: 'Versión de esquema del mapa no soportada.' };
  if (!Array.isArray(mapa.items)) return { error: 'El mapa no tiene lista de elementos.' };
  if (mapa.items.length > MAX_ITEMS_MAPA) {
    return { error: 'El mapa supera el máximo de ' + MAX_ITEMS_MAPA + ' elementos.' };
  }

  var ids = {};
  var codigos = {};
  var items = [];
  for (var i = 0; i < mapa.items.length; i++) {
    var r = limpiarItemMapa_(mapa.items[i], i, ids, codigos);
    if (r.error) return r;
    items.push(r.item);
  }

  var limpio = { esquema: 1, unidad: 'm', items: items };
  if (JSON.stringify(limpio).length > MAX_JSON_MAPA) {
    return { error: 'El mapa es demasiado grande para guardarse.' };
  }
  return { mapa: limpio };
}

function limpiarItemMapa_(it, i, ids, codigos) {
  var donde = 'Elemento ' + (i + 1);
  if (!it || typeof it !== 'object') return { error: donde + ': formato inválido.' };
  if (TIPOS_MAPA.indexOf(it.tipo) === -1) return { error: donde + ': tipo desconocido.' };
  if (typeof it.codigo === 'string' && it.codigo.trim()) donde += ' (' + it.codigo.trim().slice(0, 20) + ')';

  if (typeof it.id !== 'string' || it.id.length < 1 || it.id.length > 40) {
    return { error: donde + ': identificador inválido.' };
  }
  if (ids[it.id]) return { error: donde + ': identificador repetido.' };
  ids[it.id] = true;

  var o = { id: it.id, tipo: it.tipo };
  var err;

  if (it.tipo === 'muro' || it.tipo === 'valla') {
    err = numeros_(it, ['x1', 'y1', 'x2', 'y2'], -LIMITE_COORD, LIMITE_COORD, o, donde, 'las coordenadas');
    if (err) return err;
    err = texto_(it, 'alias', 0, 40, o, donde, 'el alias');
    if (err) return err;
    return { item: o };
  }

  err = numeros_(it, ['x', 'y'], -LIMITE_COORD, LIMITE_COORD, o, donde, 'las coordenadas');
  if (err) return err;
  if (typeof it.rot !== 'number' || !isFinite(it.rot) || it.rot < 0 || it.rot >= 360) {
    return { error: donde + ': la rotación debe estar entre 0 y 359,9°.' };
  }
  o.rot = it.rot;

  if (it.tipo === 'etiqueta') {
    err = texto_(it, 'texto', 1, 40, o, donde, 'el texto');
    if (err) return err;
    if (['S', 'M', 'L'].indexOf(it.tam) === -1) return { error: donde + ': tamaño de etiqueta inválido.' };
    o.tam = it.tam;
    return { item: o };
  }

  err = numeros_(it, ['w', 'h'], 0.1, 50, o, donde, 'el ancho y el largo');
  if (err) return err;
  err = texto_(it, 'alias', 0, 40, o, donde, 'el alias');
  if (err) return err;

  if (it.tipo === 'colmena' || it.tipo === 'nucleo') {
    err = texto_(it, 'codigo', 1, 20, o, donde, 'el código');
    if (err) return err;
    var clave = normalizar_(o.codigo);
    if (codigos[clave]) return { error: donde + ': el código ' + o.codigo + ' está repetido.' };
    codigos[clave] = true;

    var fecha = it.reina_fecha == null ? '' : it.reina_fecha;
    if (fecha !== '' && !(typeof fecha === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(fecha))) {
      return { error: donde + ': la fecha de la reina debe tener formato AAAA-MM-DD.' };
    }
    o.reina_fecha = fecha;
    err = texto_(it, 'notas', 0, 300, o, donde, 'las notas');
    if (err) return err;
  }
  return { item: o };
}

function numeros_(it, campos, min, max, o, donde, nombre) {
  for (var i = 0; i < campos.length; i++) {
    var v = it[campos[i]];
    if (typeof v !== 'number' || !isFinite(v) || v < min || v > max) {
      return {
        error: donde + ': ' + nombre + ' deben estar entre ' +
          String(min).replace('.', ',') + ' y ' + String(max).replace('.', ',') + ' m.'
      };
    }
    o[campos[i]] = v;
  }
  return null;
}

function texto_(it, campo, min, max, o, donde, nombre) {
  var v = it[campo] == null ? '' : it[campo];
  if (typeof v !== 'string') return { error: donde + ': ' + nombre + ' debe ser texto.' };
  v = v.trim();
  if (v.length < min) return { error: donde + ': falta ' + nombre + '.' };
  if (v.length > max) return { error: donde + ': ' + nombre + ' supera los ' + max + ' caracteres.' };
  o[campo] = v;
  return null;
}

function normalizar_(s) {
  return String(s).trim().toLowerCase();
}

/* ============================================================================
 *  Utilidades
 * ========================================================================== */

/** Respuesta JSON. */
function json_(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
