const test = require('node:test');
const assert = require('node:assert/strict');
const I4 = require('../assets/js/interfaz4-core.js');

// 03/10/2026 10:00 hora Argentina = 13:00 UTC
const AHORA = new Date('2026-10-03T13:00:00Z');

test('instante interpreta hora Argentina (UTC−3)', () => {
  assert.equal(I4.instante('2026-10-10', '09:00').toISOString(), '2026-10-10T12:00:00.000Z');
});

test('formatos en hora Argentina, aunque el navegador esté en otra zona', () => {
  const d = new Date('2026-10-10T00:30:00Z'); // 09/10 21:30 en Argentina
  assert.equal(I4.fmtFecha(d), '09/10/2026');
  assert.equal(I4.fmtHora(d), '21:30');
  assert.equal(I4.fmtDiaFecha(d), 'viernes 09/10/2026');
  assert.equal(I4.fmtMomento(d), 'viernes 09/10/2026 21:30');
  assert.equal(I4.fmtCorto(d), 'vie 09/10 21:30');
  assert.equal(I4.fechaAR(AHORA, 1), '2026-10-04');
  assert.equal(I4.fechaAR(new Date('2026-10-04T02:00:00Z')), '2026-10-03');
});

test('validación de fecha y hora', () => {
  assert.ok(I4.fechaValida('2026-10-10'));
  assert.ok(!I4.fechaValida('2026-02-30'));
  assert.ok(!I4.fechaValida('10/10/2026'));
  assert.ok(I4.horaValida('09:05'));
  assert.ok(!I4.horaValida('9:05'));
  assert.ok(!I4.horaValida('24:00'));
});

test('validarVisita', () => {
  const ok = { fecha: '2026-10-10', desde: '09:00', hasta: '13:00', responsable: 'Nombre', notas: '' };
  assert.deepEqual(I4.validarVisita(ok, AHORA), []);
  assert.match(I4.validarVisita({ ...ok, hasta: '08:00' }, AHORA)[0], /posterior/);
  assert.match(I4.validarVisita({ ...ok, fecha: '2026-10-03', desde: '09:00', hasta: '09:30' }, AHORA)[0], /futuro/);
  assert.match(I4.validarVisita({ ...ok, fecha: '' }, AHORA)[0], /fecha/);
  assert.match(I4.validarVisita({ ...ok, notas: 'x'.repeat(1001) }, AHORA)[0], /notas/);
});

test('agenda de informes 24 h y 12 h', () => {
  const a = I4.agendaInformes('2026-10-10', '09:00', [12, 24], AHORA);
  assert.deepEqual(a.items.map((i) => [i.horas, I4.fmtMomento(i.momento), i.vencido]), [
    [24, 'viernes 09/10/2026 09:00', false],
    [12, 'viernes 09/10/2026 21:00', false]
  ]);
  assert.equal(a.nota, '');
  const cerca = I4.agendaInformes('2026-10-03', '20:00', [24, 12], AHORA);
  assert.deepEqual(cerca.items.map((i) => i.accion), ['omitido', 'inmediato']);
  assert.equal(cerca.nota, 'El momento del informe de 12 h ya pasó: ese informe sale apenas el motor procese el registro (el de 24 h no se envía).');
  // Entre 24 h y 12 h antes: el de 24 h sale enseguida y el de 12 h a su hora (como el planificador).
  const medio = I4.agendaInformes('2026-10-04', '09:00', [24, 12], AHORA);
  assert.deepEqual(medio.items.map((i) => i.accion), ['inmediato', 'programado']);
  assert.equal(medio.nota, 'El momento del informe de 24 h ya pasó: ese informe sale apenas el motor procese el registro; el de 12 h sale a su hora.');
});

test('URL del issue precargado usa los ids de la plantilla', () => {
  const url = new URL(I4.urlNuevaVisita('eduabejas/apiario-portal', {
    apiario: 'produccion_miel', fecha: '2026-10-10', desde: '09:00', hasta: '13:00',
    responsable: ' Eduardo Mendoza ', notas: 'Revisión de núcleos & cuadros'
  }, 'Apiario de producción melífera'));
  assert.equal(url.origin + url.pathname, 'https://github.com/eduabejas/apiario-portal/issues/new');
  const p = url.searchParams;
  assert.equal(p.get('template'), 'interfaz4-visita.yml');
  assert.equal(p.get('title'), 'Interfaz 4 · Visita 2026-10-10 09:00–13:00');
  assert.equal(p.get('apiario'), 'produccion_miel — Apiario de producción melífera');
  assert.equal(p.get('fecha'), '2026-10-10');
  assert.equal(p.get('desde'), '09:00');
  assert.equal(p.get('hasta'), '13:00');
  assert.equal(p.get('responsable'), 'Eduardo Mendoza');
  assert.equal(p.get('notas'), 'Revisión de núcleos & cuadros');
});

test('URL de cancelación', () => {
  const p = new URL(I4.urlCancelar('eduabejas/apiario-portal', '2026-10-10-produccion_miel-01')).searchParams;
  assert.equal(p.get('template'), 'interfaz4-cancelar.yml');
  assert.equal(p.get('visita'), '2026-10-10-produccion_miel-01');
  assert.match(p.get('title'), /^Interfaz 4 · Cancelar visita /);
});

test('separarVisitas ordena próximas y anteriores', () => {
  const v = (id, inicio, fin, estado = 'planificada') => ({ id, inicio, fin, estado });
  const r = I4.separarVisitas([
    v('b', '2026-10-12T09:00-03:00', '2026-10-12T13:00-03:00'),
    v('a', '2026-10-10T09:00-03:00', '2026-10-10T13:00-03:00'),
    v('pasada', '2026-10-01T09:00-03:00', '2026-10-01T13:00-03:00'),
    v('cancelada', '2026-10-11T09:00-03:00', '2026-10-11T13:00-03:00', 'cancelada')
  ], AHORA);
  assert.deepEqual(r.proximas.map((x) => x.id), ['a', 'b']);
  assert.deepEqual(r.anteriores.map((x) => x.id), ['cancelada', 'pasada']);
});

test('texto de los hitos', () => {
  assert.equal(I4.textoHito({ estado: 'pendiente', programado: '2026-10-09T09:00-03:00' }), 'Pendiente · ~vie 09/10 09:00');
  assert.equal(I4.textoHito({ estado: 'enviado', momento: '2026-10-09T09:17-03:00' }), 'Enviado · vie 09/10 09:17');
  assert.equal(I4.textoHito({ estado: 'error', momento: '2026-10-09T09:17-03:00' }), 'No se pudo enviar · vie 09/10 09:17');
  assert.match(I4.textoHito({ estado: 'omitido' }), /más cercano/);
  assert.match(I4.textoHito({ estado: 'vencido_sin_envio' }), /ya había empezado/);
});

test('tiempo relativo', () => {
  assert.equal(I4.tiempoRelativo(new Date(AHORA.getTime() - 12 * 60000), AHORA), 'hace 12 min');
  assert.equal(I4.tiempoRelativo(new Date(AHORA.getTime() + 3 * 3600000), AHORA), 'en 3 h');
  assert.equal(I4.tiempoRelativo(AHORA, AHORA), 'recién');
});

test('el texto fijo de la interfaz no interpreta datos', () => {
  const fs = require('node:fs');
  const path = require('node:path');
  const archivos = ['interfaz4.html', 'assets/js/interfaz4.js', 'assets/js/interfaz4-core.js'];
  for (const a of archivos) {
    const texto = fs.readFileSync(path.join(__dirname, '..', a), 'utf8').toLowerCase();
    for (const palabra of ['recomend', 'ideal', 'riesgo', 'conviene', 'evitar', 'favorable']) {
      assert.ok(!texto.includes(palabra), `${palabra} en ${a}`);
    }
  }
});
