/**
 * Catálogo de usuarios e interfaces del portal.
 * Antes vivía en Code.gs (Apps Script); acá es la misma fuente de verdad
 * para el sitio estático, compartida por index.html e interfazN.html.
 */
window.APIARIO_USUARIOS = {
  rocio: { nombre: 'Rocío Barni', rol: 'Administrador', iniciales: 'RB' },
  eduardo: { nombre: 'Eduardo Mendoza', rol: 'Administrador', iniciales: 'EM' }
};

window.APIARIO_INTERFACES = {
  '1': { pagina: 'interfaz1.html', titulo: 'Satélites, precipitaciones y QGIS soft', icono: '🛰️' },
  '2': { pagina: 'interfaz2.html', titulo: 'Datos, precios y gráficos', icono: '📊' },
  '3': { pagina: 'interfaz3.html', titulo: 'Bitácora: registrar revisión (celular)', icono: '📋' },
  '4': { pagina: 'interfaz4.html', titulo: 'Contexto meteorológico de visitas', icono: '🌦️' },
  '5': { pagina: 'bitacoraderevision/', titulo: 'Bitácora: registros y mapa del apiario', icono: '🗺️' }
};

/** Usuario actual según ?u= en la URL, o null si no hay uno válido. */
window.apiarioUsuarioActual = function () {
  var slug = (new URLSearchParams(location.search).get('u') || '').toLowerCase();
  return window.APIARIO_USUARIOS[slug] ? Object.assign({ slug: slug }, window.APIARIO_USUARIOS[slug]) : null;
};
