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

test('completos cuenta los campos del catálogo con valor', () => {
  assert.equal(BitacoraCore.completos({}), 0);
  assert.equal(BitacoraCore.completos({ miel: 'Alto' }), 1);
  assert.equal(
    BitacoraCore.completos({ miel: 'Alto', postura: 'Sí', reina: 'Avistada', polen: 'Alta' }),
    4
  );
  // Claves fuera del catálogo no deberían contar de más.
  assert.equal(BitacoraCore.completos({ miel: 'Alto', otraCosa: 'x' }), 1);
});

test('armarPayload arma el registro con id y timestamp generados', () => {
  const payload = BitacoraCore.armarPayload({
    colmena: 'a 07',
    usuario: 'rocio',
    appVersion: 'alpha1',
    seleccion: { miel: 'Alto', postura: 'Sí', reina: 'Avistada', polen: 'Alta' }
  });
  assert.equal(payload.colmena, 'A07');
  assert.equal(payload.usuario, 'rocio');
  assert.equal(payload.app_version, 'alpha1');
  assert.equal(payload.miel, 'Alto');
  assert.match(payload.id, /^[0-9a-f-]{36}$/i);
  assert.equal(Number.isNaN(Date.parse(payload.timestamp)), false);
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
