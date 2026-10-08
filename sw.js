/**
 * Service Worker de la Bitácora de Colmenas: cachea solo su propio shell
 * (ver PRECACHE) con estrategia cache-first. La config compartida con la
 * Interfaz 5 (URL del Apps Script) va con stale-while-revalidate: anda sin
 * señal y un cambio de URL llega en la carga siguiente sin cambiar la versión.
 * Cualquier otra request (otras interfaces, CDNs, el ENDPOINT de Apps
 * Script) pasa de largo sin interceptar.
 */
importScripts('assets/js/bitacora-config.js');

var APP_VERSION = (self.BITACORA_CFG && self.BITACORA_CFG.APP_VERSION) || 'dev';
var CACHE_NAME = 'bitacora-' + APP_VERSION;

var CONFIG_COMPARTIDA = 'bitacoraderevision/assets/config.js';

var PRECACHE = [
  'interfaz3.html',
  CONFIG_COMPARTIDA,
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
var CONFIG_URL = new URL(CONFIG_COMPARTIDA, self.registration.scope).href;

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      // cache: 'reload' saltea la caché HTTP: la versión nueva baja archivos nuevos.
      .then(function (cache) {
        return cache.addAll(PRECACHE_URLS.map(function (u) { return new Request(u, { cache: 'reload' }); }));
      })
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
  // El shell se sirve igual con o sin ?u= / ?c= (los QR de las tapas abren
  // interfaz3.html?c=…): se busca en la caché por la URL sin query.
  var url = new URL(event.request.url);
  var sinQuery = url.origin + url.pathname;
  if (PRECACHE_URLS.indexOf(sinQuery) === -1) return;

  if (sinQuery === CONFIG_URL) {
    event.respondWith(
      caches.open(CACHE_NAME).then(function (cache) {
        return cache.match(CONFIG_URL).then(function (cacheada) {
          var deRed = fetch(event.request, { cache: 'no-cache' }).then(function (respuesta) {
            if (respuesta.ok) cache.put(CONFIG_URL, respuesta.clone());
            return respuesta;
          });
          if (cacheada) {
            event.waitUntil(deRed.catch(function () {}));
            return cacheada;
          }
          return deRed;
        });
      })
    );
    return;
  }

  event.respondWith(
    caches.match(sinQuery).then(function (cacheada) {
      if (cacheada) return cacheada;
      return fetch(event.request).then(function (respuesta) {
        if (respuesta.ok) {
          var copia = respuesta.clone();
          caches.open(CACHE_NAME).then(function (cache) { cache.put(sinQuery, copia); });
        }
        return respuesta;
      });
    })
  );
});
