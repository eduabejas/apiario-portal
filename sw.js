/**
 * Service Worker de la Bitácora de Colmenas: cachea solo su propio shell
 * (ver PRECACHE) con estrategia cache-first. Cualquier otra request
 * (Interfaz 1, Three.js por CDN, el ENDPOINT de Apps Script) pasa de largo
 * sin interceptar.
 */
importScripts('assets/js/bitacora-config.js');

var APP_VERSION = (self.BITACORA_CFG && self.BITACORA_CFG.APP_VERSION) || 'dev';
var CACHE_NAME = 'bitacora-' + APP_VERSION;

var PRECACHE = [
  'interfaz3.html',
  'assets/styles.css',
  'assets/alpine.min.js',
  'assets/js/usuarios.js',
  'assets/js/topbar.js',
  'assets/js/bitacora-core.js',
  'assets/js/bitacora.js',
  'assets/js/bitacora-config.js',
  'assets/vendor/gsap.min.js',
  'assets/vendor/qrcode.js',
  'assets/icons/bitacora.svg'
];

var PRECACHE_URLS = PRECACHE.map(function (p) {
  return new URL(p, self.registration.scope).href;
});

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function (cache) { return cache.addAll(PRECACHE_URLS); })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (nombres) {
        return Promise.all(
          nombres
            .filter(function (nombre) { return nombre !== CACHE_NAME; })
            .map(function (nombre) { return caches.delete(nombre); })
        );
      })
      .then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (event) {
  if (event.request.method !== 'GET') return;
  if (PRECACHE_URLS.indexOf(event.request.url) === -1) return;

  event.respondWith(
    caches.match(event.request).then(function (cacheada) {
      if (cacheada) return cacheada;
      return fetch(event.request).then(function (respuesta) {
        var copia = respuesta.clone();
        caches.open(CACHE_NAME).then(function (cache) { cache.put(event.request, copia); });
        return respuesta;
      });
    })
  );
});
