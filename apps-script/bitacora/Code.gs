const SHEET_ID = '1F2WQ-W6IuybxccTunnMFdhD-Wm6F2CttaT8NR28iVeE';
const SHEET_NAME = 'Test';
const HEADERS = ['id','timestamp','colmena','usuario','miel','postura','reina','polen','app_version','recibido'];
const ENUMS = {
  usuario: ['rocio','eduardo'],
  miel: ['Alto','Intermedio','Bajo','Nula'],
  postura: ['Sí','No'],
  reina: ['Avistada','No avistada'],
  polen: ['Alta','Baja']
};

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(10000);
    const d = JSON.parse(e.postData.contents);
    const err = validar_(d);
    if (err) return json_({ ok: false, error: err, validacion: true });
    const sh = hoja_();
    const n = sh.getLastRow() - 1;
    if (n > 0 && sh.getRange(2, 1, n, 1).getValues().flat().includes(d.id))
      return json_({ ok: true, duplicado: true, id: d.id });
    sh.appendRow([d.id, new Date(d.timestamp), d.colmena, d.usuario, d.miel,
                  d.postura, d.reina, d.polen, d.app_version || '', new Date()]);
    return json_({ ok: true, id: d.id });
  } catch (x) {
    return json_({ ok: false, error: String(x) });
  } finally {
    lock.releaseLock();
  }
}

// GET ?colmena=A07 → últimas 3 revisiones (más reciente primero)
function doGet(e) {
  const c = String((e.parameter || {}).colmena || '').toUpperCase();
  if (!/^[A-Z0-9-]{1,12}$/.test(c)) return json_({ ok: false, error: 'colmena inválida' });
  const sh = hoja_();
  const n = sh.getLastRow() - 1;
  if (n < 1) return json_({ ok: true, revisiones: [] });
  const rows = sh.getRange(2, 1, n, HEADERS.length).getValues()
    .filter(r => r[2] === c).slice(-3).reverse()
    .map(r => Object.fromEntries(HEADERS.map((h, i) => [h, r[i] instanceof Date ? r[i].toISOString() : r[i]])));
  return json_({ ok: true, revisiones: rows });
}

function validar_(d) {
  if (!d || typeof d.id !== 'string' || d.id.length > 64) return 'id';
  if (!/^[A-Z0-9-]{1,12}$/.test(d.colmena || '')) return 'colmena';
  if (isNaN(new Date(d.timestamp))) return 'timestamp';
  for (const k in ENUMS) if (!ENUMS[k].includes(d[k])) return k;
  return null;
}

function hoja_() {
  const ss = SpreadsheetApp.openById(SHEET_ID);
  const sh = ss.getSheetByName(SHEET_NAME) || ss.insertSheet(SHEET_NAME);
  if (sh.getLastRow() === 0) { sh.appendRow(HEADERS); sh.setFrozenRows(1); }
  return sh;
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
