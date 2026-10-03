/**
 * Núcleo puro de Interfaz 4: validación de visitas, agenda de informes,
 * URLs de los issues precargados y formatos en hora Argentina. Sin DOM ni
 * fetch — se testea con `node --test` y se reusa igual en el navegador.
 *
 * Argentina usa UTC−3 sin horario de verano (igual que el motor en Python).
 */
(function () {
  'use strict';

  var MS_HORA = 3600 * 1000;
  var OFFSET_AR_MS = -3 * MS_HORA;
  var DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
  var DIAS_CORTOS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];
  var ESTADOS = {
    pendiente: 'Pendiente',
    enviado: 'Enviado',
    parcial: 'Enviado en parte',
    error: 'No se pudo enviar',
    omitido: 'Omitido',
    vencido_sin_envio: 'Sin envío'
  };

  function dos(n) { return (n < 10 ? '0' : '') + n; }

  function fechaValida(texto) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(texto || '')) return false;
    var p = texto.split('-').map(Number);
    var d = new Date(Date.UTC(p[0], p[1] - 1, p[2]));
    return d.getUTCFullYear() === p[0] && d.getUTCMonth() === p[1] - 1 && d.getUTCDate() === p[2];
  }

  function horaValida(texto) { return /^([01]\d|2[0-3]):[0-5]\d$/.test(texto || ''); }

  /** '2026-10-10' + '09:00' (hora Argentina) → Date. */
  function instante(fecha, hora) { return new Date(fecha + 'T' + hora + ':00-03:00'); }

  /** Partes de calendario de un Date en hora Argentina. */
  function partes(date) {
    var d = new Date(date.getTime() + OFFSET_AR_MS);
    return {
      anio: d.getUTCFullYear(), mes: d.getUTCMonth() + 1, dia: d.getUTCDate(),
      hora: d.getUTCHours(), minuto: d.getUTCMinutes(), diaSemana: d.getUTCDay()
    };
  }

  function fmtFecha(date) { var p = partes(date); return dos(p.dia) + '/' + dos(p.mes) + '/' + p.anio; }
  function fmtHora(date) { var p = partes(date); return dos(p.hora) + ':' + dos(p.minuto); }
  function fmtDiaFecha(date) { return DIAS[partes(date).diaSemana] + ' ' + fmtFecha(date); }
  function fmtMomento(date) { return fmtDiaFecha(date) + ' ' + fmtHora(date); }
  function fmtCorto(date) {
    var p = partes(date);
    return DIAS_CORTOS[p.diaSemana] + ' ' + dos(p.dia) + '/' + dos(p.mes) + ' ' + fmtHora(date);
  }

  /** 'AAAA-MM-DD' de hoy (o de ahora + dias) en Argentina. */
  function fechaAR(ahora, dias) {
    var p = partes(new Date(ahora.getTime() + (dias || 0) * 24 * MS_HORA));
    return p.anio + '-' + dos(p.mes) + '-' + dos(p.dia);
  }

  function validarVisita(datos, ahora) {
    var errores = [];
    if (!fechaValida(datos.fecha)) errores.push('Elegí una fecha válida.');
    if (!horaValida(datos.desde)) errores.push('La hora de inicio debe tener formato HH:MM.');
    if (!horaValida(datos.hasta)) errores.push('La hora de fin debe tener formato HH:MM.');
    if (!errores.length) {
      if (datos.hasta <= datos.desde) errores.push('La hora de fin debe ser posterior a la de inicio (misma fecha).');
      else if (instante(datos.fecha, datos.desde) <= ahora) errores.push('La visita tiene que ser a futuro.');
    }
    if ((datos.responsable || '').length > 120) errores.push('El nombre del responsable es muy largo (máx. 120).');
    if ((datos.notas || '').length > 1000) errores.push('Las notas son muy largas (máx. 1000 caracteres).');
    return errores;
  }

  /**
   * Momentos de los informes (inicio − h) y qué pasa con cada uno, con la
   * misma regla que el planificador del motor: de los hitos cuyo momento ya
   * pasó se envía solo el más cercano al inicio (apenas se procesa el
   * registro) y los anteriores se omiten; los futuros salen a su hora.
   * accion: 'programado' | 'inmediato' | 'omitido'.
   */
  function agendaInformes(fecha, desde, hitos, ahora) {
    var inicio = instante(fecha, desde);
    var items = hitos.slice().sort(function (a, b) { return b - a; }).map(function (h) {
      var momento = new Date(inicio.getTime() - h * MS_HORA);
      return { horas: h, momento: momento, vencido: momento <= ahora, accion: 'programado' };
    });
    var vencidos = items.filter(function (i) { return i.vencido; });
    var nota = '';
    if (vencidos.length) {
      var inmediato = Math.min.apply(null, vencidos.map(function (i) { return i.horas; }));
      var omitidos = [];
      vencidos.forEach(function (i) {
        i.accion = i.horas === inmediato ? 'inmediato' : 'omitido';
        if (i.accion === 'omitido') omitidos.push(i.horas);
      });
      var programados = items.filter(function (i) { return !i.vencido; }).map(function (i) { return i.horas; });
      nota = 'El momento del informe de ' + inmediato + ' h ya pasó: ese informe sale apenas el motor procese el registro';
      if (omitidos.length) nota += ' (el de ' + omitidos.join(' y ') + ' h no se envía)';
      if (programados.length) nota += '; el de ' + programados.join(' y ') + ' h sale a su hora';
      nota += '.';
    }
    return { items: items, nota: nota };
  }

  function urlIssue(repo, params) {
    var q = Object.keys(params)
      .filter(function (k) { return params[k] !== undefined && params[k] !== null && params[k] !== ''; })
      .map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(params[k]); })
      .join('&');
    return 'https://github.com/' + repo + '/issues/new?' + q;
  }

  /** Issue precargado con el formulario de visita (ids de los campos de la plantilla). */
  function urlNuevaVisita(repo, datos, nombreApiario) {
    return urlIssue(repo, {
      template: 'interfaz4-visita.yml',
      title: 'Interfaz 4 · Visita ' + datos.fecha + ' ' + datos.desde + '–' + datos.hasta,
      apiario: datos.apiario + (nombreApiario ? ' — ' + nombreApiario : ''),
      fecha: datos.fecha,
      desde: datos.desde,
      hasta: datos.hasta,
      responsable: (datos.responsable || '').trim(),
      notas: (datos.notas || '').trim()
    });
  }

  function urlCancelar(repo, visitaId) {
    return urlIssue(repo, {
      template: 'interfaz4-cancelar.yml',
      title: 'Interfaz 4 · Cancelar visita ' + visitaId,
      visita: visitaId
    });
  }

  function etiquetaEstado(estado) { return ESTADOS[estado] || estado; }

  /** Próximas (planificadas que no terminaron) y anteriores (el resto). */
  function separarVisitas(visitas, ahora) {
    var proximas = [], anteriores = [];
    (visitas || []).forEach(function (v) {
      if (v.estado === 'planificada' && new Date(v.fin) > ahora) proximas.push(v);
      else anteriores.push(v);
    });
    proximas.sort(function (a, b) { return new Date(a.inicio) - new Date(b.inicio); });
    anteriores.sort(function (a, b) { return new Date(b.inicio) - new Date(a.inicio); });
    return { proximas: proximas, anteriores: anteriores };
  }

  /** Texto corto del estado de un hito para la lista de visitas. */
  function textoHito(h) {
    var base = etiquetaEstado(h.estado);
    if (h.estado === 'pendiente' && h.programado) return base + ' · ~' + fmtCorto(new Date(h.programado));
    if ((h.estado === 'enviado' || h.estado === 'parcial' || h.estado === 'error') && h.momento) {
      return base + ' · ' + fmtCorto(new Date(h.momento));
    }
    if (h.estado === 'omitido') return base + ' (se envió el más cercano al inicio)';
    if (h.estado === 'vencido_sin_envio') return base + ' (la visita ya había empezado)';
    return base;
  }

  function tiempoRelativo(date, ahora) {
    var min = Math.round((ahora - date) / 60000);
    if (Math.abs(min) < 1) return 'recién';
    var futuro = min < 0;
    min = Math.abs(min);
    var texto = min < 60 ? min + ' min' : (min < 48 * 60 ? Math.round(min / 60) + ' h' : Math.round(min / 1440) + ' días');
    return futuro ? 'en ' + texto : 'hace ' + texto;
  }

  var api = {
    fechaValida: fechaValida, horaValida: horaValida, instante: instante, partes: partes,
    fmtFecha: fmtFecha, fmtHora: fmtHora, fmtDiaFecha: fmtDiaFecha, fmtMomento: fmtMomento, fmtCorto: fmtCorto,
    fechaAR: fechaAR, validarVisita: validarVisita, agendaInformes: agendaInformes,
    urlNuevaVisita: urlNuevaVisita, urlCancelar: urlCancelar, etiquetaEstado: etiquetaEstado,
    separarVisitas: separarVisitas, textoHito: textoHito, tiempoRelativo: tiempoRelativo
  };

  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.Interfaz4Core = api;
})();
