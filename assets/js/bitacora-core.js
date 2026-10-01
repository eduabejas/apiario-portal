/**
 * Núcleo puro de la Bitácora de Colmenas: catálogo de campos, normalización
 * de IDs y outbox offline. Sin DOM, sin fetch — así se puede testear con
 * `node --test` y se reusa igual en el navegador.
 */
(function () {
  "use strict";

  var CAMPOS = [
    {
      key: 'miel',
      etiqueta: 'Reservas de miel',
      opciones: [
        { valor: 'Alto', tono: 'ok' },
        { valor: 'Intermedio', tono: 'medio' },
        { valor: 'Bajo', tono: 'alerta' },
        { valor: 'Nula', tono: 'critico' }
      ]
    },
    {
      key: 'postura',
      etiqueta: 'Postura',
      opciones: [
        { valor: 'Sí', tono: 'ok' },
        { valor: 'No', tono: 'critico' }
      ]
    },
    {
      key: 'reina',
      etiqueta: 'Reina',
      opciones: [
        { valor: 'Avistada', tono: 'ok' },
        { valor: 'No avistada', tono: 'neutro' }
      ]
    },
    {
      key: 'polen',
      etiqueta: 'Reservas de polen',
      opciones: [
        { valor: 'Alta', tono: 'ok' },
        { valor: 'Baja', tono: 'alerta' }
      ]
    }
  ];

  var ID_VALIDO = /^[A-Z0-9-]{1,12}$/;

  /** 'a 07' → 'A07'. Mayúsculas, sin espacios. No valida formato. */
  function normalizarId(valor) {
    return String(valor == null ? '' : valor).trim().toUpperCase().replace(/\s+/g, '');
  }

  function idValido(valor) {
    return ID_VALIDO.test(valor);
  }

  /**
   * Siguiente ID incrementando el último grupo de dígitos y conservando
   * el padding: A07→A08, B-009→B-010, A99→A100. Sin dígitos → null.
   */
  function siguienteId(id) {
    var m = /^(.*?)(\d+)$/.exec(String(id || ''));
    if (!m) return null;
    var prefijo = m[1];
    var digitos = m[2];
    var siguiente = String(parseInt(digitos, 10) + 1).padStart(digitos.length, '0');
    return prefijo + siguiente;
  }

  /** Arma el payload que viaja al endpoint a partir de la selección actual. */
  function armarPayload(datos) {
    var sel = datos.seleccion || {};
    return {
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      colmena: normalizarId(datos.colmena),
      usuario: datos.usuario,
      miel: sel.miel,
      postura: sel.postura,
      reina: sel.reina,
      polen: sel.polen,
      app_version: datos.appVersion
    };
  }

  /** Cuántos de los CAMPOS ya tienen valor elegido en `sel`. */
  function completos(sel) {
    sel = sel || {};
    var n = 0;
    for (var i = 0; i < CAMPOS.length; i++) {
      if (sel[CAMPOS[i].key]) n++;
    }
    return n;
  }

  /**
   * Outbox offline sobre un storage inyectable (localStorage o un mock en
   * memoria para tests), tipo `{getItem(key), setItem(key, valor)}`.
   */
  function crearOutbox(storage, key) {
    key = key || 'bitacora_outbox';

    function leer() {
      try {
        var crudo = storage.getItem(key);
        return crudo ? JSON.parse(crudo) : [];
      } catch (err) {
        return [];
      }
    }

    function escribir(lista) {
      storage.setItem(key, JSON.stringify(lista));
    }

    function agregar(registro) {
      var lista = leer();
      lista.push(Object.assign({ estado: 'pendiente' }, registro));
      escribir(lista);
      return lista;
    }

    function quitar(id) {
      var lista = leer().filter(function (r) { return r.id !== id; });
      escribir(lista);
      return lista;
    }

    function marcarRechazado(id, motivo) {
      var lista = leer().map(function (r) {
        return r.id === id ? Object.assign({}, r, { estado: 'rechazado', motivo: motivo || '' }) : r;
      });
      escribir(lista);
      return lista;
    }

    return { leer: leer, agregar: agregar, quitar: quitar, marcarRechazado: marcarRechazado };
  }

  var BitacoraCore = {
    CAMPOS: CAMPOS,
    idValido: idValido,
    normalizarId: normalizarId,
    siguienteId: siguienteId,
    armarPayload: armarPayload,
    completos: completos,
    crearOutbox: crearOutbox
  };

  if (typeof window !== 'undefined') window.BitacoraCore = BitacoraCore;
  if (typeof module !== 'undefined') module.exports = BitacoraCore;
})();
