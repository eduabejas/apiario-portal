const test = require('node:test');
const assert = require('node:assert/strict');
const BitacoraCore = require('../assets/js/bitacora-core.js');

test('normalizarId pasa a mayúsculas y saca espacios', () => {
  assert.equal(BitacoraCore.normalizarId('a 07'), 'A07');
  assert.equal(BitacoraCore.normalizarId('  b-009 '), 'B-009');
});

test('idValido acepta y rechaza según el patrón esperado', () => {
  assert.equal(BitacoraCore.idValido('A07'), true);
  assert.equal(BitacoraCore.idValido('B-009'), true);
  assert.equal(BitacoraCore.idValido(''), false);
  assert.equal(BitacoraCore.idValido('A 07'), false);
  assert.equal(BitacoraCore.idValido('COLMENA-DEMASIADO-LARGA'), false);
  assert.equal(BitacoraCore.idValido('ñ07'), false);
});

test('siguienteId incrementa el último grupo de dígitos conservando el padding', () => {
  assert.equal(BitacoraCore.siguienteId('A07'), 'A08');
  assert.equal(BitacoraCore.siguienteId('B-009'), 'B-010');
  assert.equal(BitacoraCore.siguienteId('A99'), 'A100');
  assert.equal(BitacoraCore.siguienteId('ABC'), null);
});

test('el catálogo usa las mismas columnas y valores que la hoja de la Interfaz 5', () => {
  assert.deepEqual(BitacoraCore.CAMPOS.map((c) => c.key), [
    'postura', 'estado_reina', 'cria_operculada', 'reservas_miel', 'reservas_polen', 'poblacion',
    'reina_vista', 'huevos', 'temperamento', 'sanidad', 'celdas_reales'
  ]);
  const opciones = (key) => BitacoraCore.CAMPOS.find((c) => c.key === key).opciones.map((o) => o.valor);
  assert.deepEqual(opciones('postura'), ['Alta', 'Media', 'Baja']);
  assert.deepEqual(opciones('reservas_miel'), ['Alta', 'Media', 'Baja', 'Nula']);
  assert.deepEqual(opciones('reina_vista'), ['Sí', 'No', 'No buscada']);
  assert.deepEqual(opciones('celdas_reales'), ['No', 'Enjambrazón', 'Supersedura', 'Emergencia']);
  for (const c of BitacoraCore.CAMPOS) {
    assert.ok(BitacoraCore.GRUPOS.some((g) => g.key === c.grupo), c.key);
    assert.ok(c.corto, c.key);
  }
});

test('completos cuenta los campos del catálogo con valor', () => {
  assert.equal(BitacoraCore.completos({}), 0);
  assert.equal(BitacoraCore.completos({ postura: 'Alta' }), 1);
  assert.equal(BitacoraCore.completos({ postura: 'Alta', reservas_miel: 'Nula', huevos: 'Sí' }), 3);
  // Claves fuera del catálogo o vacías no cuentan.
  assert.equal(BitacoraCore.completos({ postura: 'Alta', otraCosa: 'x', sanidad: '' }), 1);
});

test('hayDatos: alcanza con un campo, varroa, acaricida, una acción o una nota', () => {
  assert.equal(BitacoraCore.hayDatos({}), false);
  assert.equal(BitacoraCore.hayDatos({ seleccion: { sanidad: '' }, varroa: ' ', observaciones: '  ' }), false);
  assert.equal(BitacoraCore.hayDatos({ seleccion: { huevos: 'Sí' } }), true);
  assert.equal(BitacoraCore.hayDatos({ varroa: '0' }), true);
  assert.equal(BitacoraCore.hayDatos({ acaricida: 'Timol' }), true);
  assert.equal(BitacoraCore.hayDatos({ acciones: ['Alimentó'] }), true);
  assert.equal(BitacoraCore.hayDatos({ observaciones: 'tranquila' }), true);
});

test('leerVarroa acepta coma o punto, redondea a un decimal y valida el rango', () => {
  assert.deepEqual(BitacoraCore.leerVarroa(''), { valor: null, error: '' });
  assert.deepEqual(BitacoraCore.leerVarroa('2,4'), { valor: 2.4, error: '' });
  assert.deepEqual(BitacoraCore.leerVarroa(' 3.06 '), { valor: 3.1, error: '' });
  assert.deepEqual(BitacoraCore.leerVarroa('0'), { valor: 0, error: '' });
  assert.equal(BitacoraCore.leerVarroa('101').valor, null);
  assert.match(BitacoraCore.leerVarroa('101').error, /entre 0 y 100/);
  assert.match(BitacoraCore.leerVarroa('abc').error, /entre 0 y 100/);
  assert.match(BitacoraCore.leerVarroa('-1').error, /entre 0 y 100/);
});

test('tonoVarroa: verde < 2, ámbar 2–<3, rojo ≥ 3', () => {
  assert.equal(BitacoraCore.tonoVarroa(0), 'ok');
  assert.equal(BitacoraCore.tonoVarroa(1.9), 'ok');
  assert.equal(BitacoraCore.tonoVarroa(2), 'medio');
  assert.equal(BitacoraCore.tonoVarroa(2.9), 'medio');
  assert.equal(BitacoraCore.tonoVarroa(3), 'critico');
});

test('armarPayload arma el registro con los datos que espera el Apps Script', () => {
  const payload = BitacoraCore.armarPayload({
    colmena: 'c- 01',
    usuario: 'rocio',
    registradoPor: 'Rocío Barni',
    appVersion: 'beta1',
    fecha: '2026-10-08',
    apiario: '  Norte ',
    seleccion: { postura: 'Alta', huevos: 'Sí', sanidad: '' },
    varroa: '2,45',
    acaricida: ' Timol ',
    acciones: ['Limpieza', 'Trató varroa', 'Inventada'],
    observaciones: ' reina nueva '
  });
  assert.match(payload.id, /^[0-9a-f-]{36}$/i);
  assert.equal(Number.isNaN(Date.parse(payload.timestamp)), false);
  assert.equal(payload.colmena, 'C-01');
  assert.equal(payload.usuario, 'rocio');
  assert.equal(payload.app_version, 'beta1');
  const d = payload.datos;
  assert.equal(d.id_cliente, payload.id);
  assert.equal(d.numero_colmena, 'C-01');
  assert.equal(d.fecha, '2026-10-08');
  assert.equal(d.apiario, 'Norte');
  assert.equal(d.registrado_por, 'Rocío Barni');
  assert.equal(d.postura, 'Alta');
  assert.equal(d.huevos, 'Sí');
  assert.equal(d.sanidad, '');
  assert.equal(d.estado_reina, '');
  assert.equal(d.varroa_pct, 2.5);
  assert.equal(d.acaricida, 'Timol');
  // Solo acciones del catálogo y en su orden.
  assert.deepEqual(d.acciones, ['Trató varroa', 'Limpieza']);
  assert.equal(d.observaciones, 'reina nueva');
  // Sin análisis de varroa viaja vacío (la hoja lo guarda en blanco).
  assert.equal(BitacoraCore.armarPayload({ colmena: 'A1', seleccion: {} }).datos.varroa_pct, '');
});

test('ultimasPorColmena se queda con la revisión más reciente de cada colmena', () => {
  const ultimas = BitacoraCore.ultimasPorColmena([
    { numero_colmena: 'c-01', fecha: '2026-10-01', creado_en: '2026-10-01T10:00:00Z', postura: 'Baja' },
    { numero_colmena: 'C-01', fecha: '2026-10-05', creado_en: '2026-10-05T10:00:00Z', postura: 'Alta' },
    { numero_colmena: 'C-01', fecha: '2026-10-05', creado_en: '2026-10-05T09:00:00Z', postura: 'Media' },
    { numero_colmena: 'C-02', fecha: '2026-09-30', postura: 'Media' },
    { numero_colmena: '', fecha: '2026-10-05' }
  ]);
  assert.deepEqual(Object.keys(ultimas).sort(), ['C-01', 'C-02']);
  assert.equal(ultimas['C-01'].postura, 'Alta');
  assert.equal(ultimas['C-02'].postura, 'Media');
});

test('codigosDelMapa toma colmenas y núcleos, normalizados y en orden humano', () => {
  const codigos = BitacoraCore.codigosDelMapa({
    ok: true,
    version: 3,
    data: { items: [
      { tipo: 'colmena', codigo: 'C-10' },
      { tipo: 'nucleo', codigo: 'n-1' },
      { tipo: 'colmena', codigo: 'C-2' },
      { tipo: 'pallet', codigo: 'P-1' },
      { tipo: 'colmena', codigo: 'c-2' },
      { tipo: 'colmena', codigo: 'con espacio largo de más' }
    ] }
  });
  assert.deepEqual(codigos, ['C-2', 'C-10', 'N-1']);
  assert.deepEqual(BitacoraCore.codigosDelMapa({ ok: true, data: [] }), []);
});

test('siguienteColmena sigue el orden del mapa y si no, el número siguiente', () => {
  const mapa = ['C-10', 'C-2', 'N-1'];
  assert.equal(BitacoraCore.siguienteColmena('C-2', mapa), 'C-10');
  assert.equal(BitacoraCore.siguienteColmena('C-10', mapa), 'N-1');
  assert.equal(BitacoraCore.siguienteColmena('N-1', mapa), null);
  assert.equal(BitacoraCore.siguienteColmena('A07', mapa), 'A08');
  assert.equal(BitacoraCore.siguienteColmena('A07', []), 'A08');
});

test('clasificarRespuesta distingue código inválido, dato rechazado y error para reintentar', () => {
  assert.equal(BitacoraCore.clasificarRespuesta({ ok: true, id: 'x' }), 'ok');
  assert.equal(BitacoraCore.clasificarRespuesta({ ok: true, id: 'x', duplicado: true }), 'ok');
  assert.equal(BitacoraCore.clasificarRespuesta({ ok: false, error: 'Código de acceso inválido.' }), 'codigo');
  assert.equal(BitacoraCore.clasificarRespuesta({ ok: false, error: 'Faltan datos obligatorios (colmena y fecha).' }), 'rechazado');
  assert.equal(BitacoraCore.clasificarRespuesta({ ok: false, error: 'El análisis de varroa debe ser un número entre 0 y 100.' }), 'rechazado');
  assert.equal(BitacoraCore.clasificarRespuesta({ ok: false, error: 'El código no está configurado en el servidor.' }), 'pendiente');
  assert.equal(BitacoraCore.clasificarRespuesta({ ok: false, error: 'Exception: Lock timeout' }), 'pendiente');
  assert.equal(BitacoraCore.clasificarRespuesta(null), 'pendiente');
});

function storageEnMemoria() {
  const datos = {};
  return {
    getItem: (k) => (Object.prototype.hasOwnProperty.call(datos, k) ? datos[k] : null),
    setItem: (k, v) => { datos[k] = v; }
  };
}

test('outbox: ciclo agregar → quitar', () => {
  const outbox = BitacoraCore.crearOutbox(storageEnMemoria());
  assert.deepEqual(outbox.leer(), []);

  outbox.agregar({ id: '1', colmena: 'A07' });
  outbox.agregar({ id: '2', colmena: 'A08' });
  let lista = outbox.leer();
  assert.equal(lista.length, 2);
  assert.equal(lista[0].estado, 'pendiente');

  lista = outbox.quitar('1');
  assert.equal(lista.length, 1);
  assert.equal(lista[0].id, '2');
});

test('outbox: marcarRechazado deja el registro con motivo y no lo borra', () => {
  const outbox = BitacoraCore.crearOutbox(storageEnMemoria());
  outbox.agregar({ id: '9', colmena: 'B-009' });

  const lista = outbox.marcarRechazado('9', 'colmena');
  assert.equal(lista.length, 1);
  assert.equal(lista[0].estado, 'rechazado');
  assert.equal(lista[0].motivo, 'colmena');
});

test('outbox: cada instancia usa su propia clave de storage', () => {
  const storage = storageEnMemoria();
  const a = BitacoraCore.crearOutbox(storage, 'outbox_a');
  const b = BitacoraCore.crearOutbox(storage, 'outbox_b');
  a.agregar({ id: 'x' });
  assert.deepEqual(a.leer().map((r) => r.id), ['x']);
  assert.deepEqual(b.leer(), []);
});
