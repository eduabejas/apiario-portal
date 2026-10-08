/**
 * Config de la Bitácora (Interfaz 3). El ENDPOINT es la misma app web de
 * Google que usa la Interfaz 5 (bitácora de revisión + mapa): la URL se pega
 * una sola vez en bitacoraderevision/assets/config.js. Sin URL = modo demo.
 * También lo importa sw.js (sin window), que solo usa APP_VERSION.
 */
(function (raiz) {
  var url = (raiz.APP_CONFIG && raiz.APP_CONFIG.WEBAPP_URL) || '';
  if (url.indexOf('PEGA-AQUI') !== -1) url = '';
  raiz.BITACORA_CFG = { ENDPOINT: url, APP_VERSION: 'beta1' };
})(typeof window !== 'undefined' ? window : self);
