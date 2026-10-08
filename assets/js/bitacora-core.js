/**
 * Núcleo puro de la Bitácora de Colmenas: catálogo de campos, normalización
 * de IDs, armado del registro y outbox offline. Sin DOM, sin fetch — así se
 * puede testear con `node --test` y se reusa igual en el navegador.
 *
 * Los campos y valores son los mismos que guarda el Apps Script de la
 * bitácora de revisión (bitacoraderevision/apps-script/Codigo.gs) y que
 * muestra la Interfaz 5: `key` es el nombre de la columna en la hoja.
 */
(function () {
  "use strict";

  function op(valor, tono) { return { valor: valor, tono: tono }; }

  var CAMPOS = [
    { key: 'postura', grupo: 'evaluacion', etiqueta: 'Postura', corto: 'Postura',
      opciones: [op('Alta', 'ok'), op('Media', 'medio'), op('Baja', 'alerta')] },
    { key: 'estado_reina', grupo: 'evaluacion', etiqueta: 'Estado de la reina', corto: 'Reina',
      opciones: [op('Excelente', 'ok'), op('Regular', 'medio'), op('Mala', 'critico')] },
    { key: 'cria_operculada', grupo: 'evaluacion', etiqueta: 'Cría operculada', corto: 'Cría operc.',
      opciones: [op('Alta', 'ok'), op('Media', 'medio'), op('Baja', 'alerta')] },
    { key: 'reservas_miel', grupo: 'evaluacion', etiqueta: 'Reservas de miel', corto: 'Miel',
      opciones: [op('Alta', 'ok'), op('Media', 'medio'), op('Baja', 'alerta'), op('Nula', 'critico')] },
    { key: 'reservas_polen', grupo: 'evaluacion', etiqueta: 'Reservas de polen', corto: 'Polen',
      opciones: [op('Alta', 'ok'), op('Media', 'medio'), op('Baja', 'alerta')] },
    { key: 'poblacion', grupo: 'evaluacion', etiqueta: 'Población / fortaleza', corto: 'Población',
      opciones: [op('Fuerte', 'ok'), op('Media', 'medio'), op('Débil', 'alerta')] },
    { key: 'reina_vista', grupo: 'observacion', etiqueta: 'Reina vista', corto: 'Reina vista',
      opciones: [op('Sí', 'ok'), op('No', 'alerta'), op('No buscada', 'neutro')] },
    { key: 'huevos', grupo: 'observacion', etiqueta: 'Presencia de huevos', corto: 'Huevos',
      opciones: [op('Sí', 'ok'), op('No', 'critico')] },
    { key: 'temperamento', grupo: 'observacion', etiqueta: 'Temperamento', corto: 'Temperam.',
      opciones: [op('Manso', 'ok'), op('Normal', 'medio'), op('Agresivo', 'alerta')] },
    { key: 'sanidad', grupo: 'observacion', etiqueta: 'Sanidad (varroa, polilla…)', corto: 'Sanidad',
      opciones: [op('Sin signos', 'ok'), op('Leve', 'medio'), op('Alta', 'critico')] },
    { key: 'celdas_reales', grupo: 'observacion', etiqueta: 'Celdas reales', corto: 'Celdas real.',
      opciones: [op('No', 'ok'), op('Enjambrazón', 'critico'), op('Supersedura', 'medio'), op('Emergencia', 'critico')] }
  ];

  var GRUPOS = [
    { key: 'evaluacion', titulo: 'Evaluación de la colmena' },
    { key: 'observacion', titulo: 'Observación de campo' }
  ];

  var ACARICIDAS = ['Ácido oxálico', 'Ácido fórmico', 'Timol', 'Amitraz', 'Flumetrina'];
  var ACCIONES = ['Alimentó', 'Agregó alza', 'Trató varroa', 'Cambió reina', 'Dividió', 'Cosechó', 'Limpieza'];

  // Varroa (%): verde < 2, ámbar 2–<3, rojo ≥ 3 (mismos umbrales que la Interfaz 5).
  var VARROA_ATENCION = 2.0;
  var VARROA_ALERTA = 3.0;

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

  /** Orden "humano" de códigos: C-2 antes que C-10. */
  function compararCodigos(a, b) {
    return String(a).localeCompare(String(b), 'es', { numeric: true });
  }

  /**
   * Siguiente colmena a revisar: si `id` está en la lista de códigos del
   * mapa, la que le sigue en ese orden (null si es la última); si no, el
   * siguiente número (siguienteId).
   */
  function siguienteColmena(id, codigos) {
    var lista = (codigos || []).slice().sort(compararCodigos);
    var i = lista.indexOf(id);
    if (i === -1) return siguienteId(id);
    return i + 1 < lista.length ? lista[i + 1] : null;
  }

  /** Fecha local de hoy (o de `fecha`) como 'AAAA-MM-DD'. */
  function fechaISO(fecha) {
    var d = fecha || new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  }

  /**
   * Lee el análisis de varroa escrito a mano ('2,4', '2.4', '').
   * → { valor: número redondeado a 1 decimal | null, error: texto | '' }
   */
  function leerVarroa(texto) {
    var t = String(texto == null ? '' : texto).trim();
    if (t === '') return { valor: null, error: '' };
    var n = Number(t.replace(',', '.'));
    if (!isFinite(n) || n < 0 || n > 100) {
      return { valor: null, error: 'El análisis de varroa debe ser un número entre 0 y 100.' };
    }
    return { valor: Math.round(n * 10) / 10, error: '' };
  }

  function tonoVarroa(pct) {
    if (pct >= VARROA_ALERTA) return 'critico';
    if (pct >= VARROA_ATENCION) return 'medio';
    return 'ok';
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

  /** ¿La revisión en curso tiene al menos un dato cargado? */
  function hayDatos(form) {
    form = form || {};
    return completos(form.seleccion) > 0 ||
      String(form.varroa || '').trim() !== '' ||
      String(form.acaricida || '').trim() !== '' ||
      (form.acciones || []).length > 0 ||
      String(form.observaciones || '').trim() !== '';
  }

  function texto(valor, max) {
    return String(valor == null ? '' : valor).trim().slice(0, max);
  }

  /**
   * Arma el registro que va a la outbox. `datos` es exactamente lo que
   * recibe el Apps Script ({ codigo, datos }); `id_cliente` le permite
   * descartar un reintento que ya había llegado.
   */
  function armarPayload(form) {
    var sel = form.seleccion || {};
    var id = crypto.randomUUID();
    var varroa = leerVarroa(form.varroa);
    var acciones = ACCIONES.filter(function (a) { return (form.acciones || []).indexOf(a) !== -1; });
    var datos = {
      id_cliente: id,
      fecha: form.fecha || fechaISO(),
      numero_colmena: normalizarId(form.colmena),
      apiario: texto(form.apiario, 80),
      registrado_por: texto(form.registradoPor, 80),
      varroa_pct: varroa.valor === null ? '' : varroa.valor,
      acaricida: texto(form.acaricida, 60),
      acciones: acciones,
      observaciones: texto(form.observaciones, 2000)
    };
    for (var i = 0; i < CAMPOS.length; i++) datos[CAMPOS[i].key] = sel[CAMPOS[i].key] || '';
    return {
      id: id,
      timestamp: new Date().toISOString(),
      colmena: datos.numero_colmena,
      usuario: form.usuario || '',
      app_version: form.appVersion,
      datos: datos
    };
  }

  /** Más reciente primero: por fecha de revisión y, a igual fecha, por carga. */
  function masReciente(a, b) {
    var fa = String(a.fecha || ''), fb = String(b.fecha || '');
    if (fa !== fb) return fa > fb ? a : b;
    return String(a.creado_en || '') >= String(b.creado_en || '') ? a : b;
  }

  /** { 'C-01': última revisión de esa colmena, … } a partir de la hoja. */
  function ultimasPorColmena(revisiones) {
    var mapa = {};
    (Array.isArray(revisiones) ? revisiones : []).forEach(function (r) {
      var id = normalizarId(r && r.numero_colmena);
      if (!id) return;
      mapa[id] = mapa[id] ? masReciente(mapa[id], r) : r;
    });
    return mapa;
  }

  /** Códigos de colmenas y núcleos del mapa (GET ?recurso=mapa), ordenados. */
  function codigosDelMapa(respuesta) {
    var items = respuesta && respuesta.data && Array.isArray(respuesta.data.items) ? respuesta.data.items : [];
    var vistos = {};
    return items
      .filter(function (it) { return it && (it.tipo === 'colmena' || it.tipo === 'nucleo'); })
      .map(function (it) { return normalizarId(it.codigo); })
      .filter(function (c) {
        if (!c || !idValido(c) || vistos[c]) return false;
        vistos[c] = true;
        return true;
      })
      .sort(compararCodigos);
  }

  /**
   * Qué hacer con la respuesta del Apps Script a un registro:
   * 'ok' | 'codigo' (código inválido: pedirlo de nuevo) |
   * 'rechazado' (dato inválido: no tiene sentido reintentar) |
   * 'pendiente' (falla del servidor: reintentar más tarde).
   */
  function clasificarRespuesta(res) {
    if (res && res.ok) return 'ok';
    var msg = String((res && res.error) || '');
    if (/c[oó]digo de acceso inv[aá]lido/i.test(msg)) return 'codigo';
    if (/faltan datos|varroa/i.test(msg)) return 'rechazado';
    return 'pendiente';
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
    GRUPOS: GRUPOS,
    ACARICIDAS: ACARICIDAS,
    ACCIONES: ACCIONES,
    VARROA_ATENCION: VARROA_ATENCION,
    VARROA_ALERTA: VARROA_ALERTA,
    idValido: idValido,
    normalizarId: normalizarId,
    siguienteId: siguienteId,
    siguienteColmena: siguienteColmena,
    compararCodigos: compararCodigos,
    fechaISO: fechaISO,
    leerVarroa: leerVarroa,
    tonoVarroa: tonoVarroa,
    completos: completos,
    hayDatos: hayDatos,
    armarPayload: armarPayload,
    ultimasPorColmena: ultimasPorColmena,
    masReciente: masReciente,
    codigosDelMapa: codigosDelMapa,
    clasificarRespuesta: clasificarRespuesta,
    crearOutbox: crearOutbox
  };

  if (typeof window !== 'undefined') window.BitacoraCore = BitacoraCore;
  if (typeof module !== 'undefined') module.exports = BitacoraCore;
})();
