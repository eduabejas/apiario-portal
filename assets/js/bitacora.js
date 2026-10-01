/**
 * Bitácora de colmenas: store de Alpine, outbox offline, envío al endpoint
 * y animaciones GSAP. Reusa window.APIARIO_USUARIOS/apiarioUsuarioActual
 * (usuarios.js), window.apiarioRenderChip (topbar.js), window.BitacoraCore
 * (bitacora-core.js) y window.BITACORA_CFG (bitacora-config.js).
 */
(function () {
  "use strict";

  var Core = window.BitacoraCore;
  var CFG = window.BITACORA_CFG || { ENDPOINT: '', APP_VERSION: 'dev' };

  var LS_USUARIO = 'bitacora_usuario';
  var LS_RECIENTES = 'bitacora_colmenas_recientes';

  var TONO_CLASES = {
    ok: 'bg-ok text-white border-ok',
    medio: 'bg-medio text-tinta border-medio',
    alerta: 'bg-alerta text-white border-alerta',
    critico: 'bg-critico text-white border-critico',
    neutro: 'bg-neutro text-white border-neutro'
  };

  // --- Storage resistente (localStorage puede tirar en modo privado) ---
  function storageSeguro() {
    try {
      var k = '__bitacora_test__';
      window.localStorage.setItem(k, '1');
      window.localStorage.removeItem(k);
      return window.localStorage;
    } catch (err) {
      var mem = {};
      return {
        getItem: function (key) { return Object.prototype.hasOwnProperty.call(mem, key) ? mem[key] : null; },
        setItem: function (key, valor) { mem[key] = valor; }
      };
    }
  }
  var storage = storageSeguro();
  var outbox = Core.crearOutbox(storage, 'bitacora_outbox');

  // --- Usuario: ?u= → localStorage → selector. Se resuelve ya, antes de
  // DOMContentLoaded, para que topbar.js (que sí corre en DOMContentLoaded)
  // vea la URL ya corregida y pinte el chip bien a la primera. ---
  function usuarioSlugActivo() {
    var params = new URLSearchParams(location.search);
    var candidato = (params.get('u') || '').toLowerCase();
    if (window.APIARIO_USUARIOS && window.APIARIO_USUARIOS[candidato]) return candidato;
    var guardado = storage.getItem(LS_USUARIO);
    if (guardado && window.APIARIO_USUARIOS && window.APIARIO_USUARIOS[guardado]) return guardado;
    return null;
  }

  function actualizarParam(nombre, valor) {
    var params = new URLSearchParams(location.search);
    if (valor === null) params.delete(nombre); else params.set(nombre, valor);
    var qs = params.toString();
    history.replaceState(null, '', location.pathname + (qs ? '?' + qs : ''));
  }

  (function resolverUsuarioInicial() {
    var slug = usuarioSlugActivo();
    if (!slug) return;
    if ((new URLSearchParams(location.search).get('u') || '').toLowerCase() !== slug) {
      actualizarParam('u', slug);
    }
    storage.setItem(LS_USUARIO, slug);
  })();

  function leerRecientes() {
    try { return JSON.parse(storage.getItem(LS_RECIENTES) || '[]'); } catch (err) { return []; }
  }
  function agregarReciente(id) {
    var lista = leerRecientes().filter(function (x) { return x !== id; });
    lista.unshift(id);
    lista = lista.slice(0, 6);
    storage.setItem(LS_RECIENTES, JSON.stringify(lista));
    return lista;
  }

  function tiempoRelativo(iso) {
    if (!iso) return '';
    var ms = Date.now() - new Date(iso).getTime();
    var min = Math.round(ms / 60000);
    if (min < 1) return 'recién';
    if (min < 60) return 'hace ' + min + ' min';
    var horas = Math.round(min / 60);
    if (horas < 24) return 'hace ' + horas + (horas === 1 ? ' hora' : ' horas');
    var dias = Math.round(horas / 24);
    return 'hace ' + dias + (dias === 1 ? ' día' : ' días');
  }

  function svgQrPara(id) {
    if (typeof qrcode === 'undefined') return '';
    var url = location.origin + location.pathname + '?c=' + encodeURIComponent(id);
    var qr = qrcode(0, 'M');
    qr.addData(url);
    qr.make();
    return qr.createSvgTag({ scalable: true, margin: 1 });
  }

  // =====================================================================
  // Animaciones GSAP — todo transform/opacity/clip-path, salvo el "dibujado"
  // de trazos (check, hexágono) con strokeDashoffset, que es la técnica
  // estándar para ese efecto y la que pide la bitácora. Dos variantes según
  // prefers-reduced-motion, registradas con gsap.matchMedia().
  // =====================================================================
  var anim = {
    entradaRevision: function () {},
    seleccionBoton: function () {},
    dibujarCheck: function (path) { if (path) path.style.strokeDashoffset = 0; },
    progreso: function () {},
    pulsoGuardar: function () {},
    abrirHoja: function (panel, fondo) { if (panel) panel.style.transform = ''; if (fondo) fondo.style.opacity = 1; },
    cerrarHoja: function (panel, fondo, onComplete) { onComplete(); },
    exito: function (refs) {
      if (refs.outline) refs.outline.style.strokeDashoffset = 0;
      if (refs.check) refs.check.style.strokeDashoffset = 0;
    }
  };

  if (typeof gsap !== 'undefined') {
    var mm = gsap.matchMedia();

    mm.add('(prefers-reduced-motion: no-preference)', function () {
      anim.entradaRevision = function (tarjetas) {
        if (!tarjetas.length) return;
        gsap.fromTo(tarjetas, { y: 16, opacity: 0 }, { y: 0, opacity: 1, duration: 0.35, stagger: 0.06, ease: 'power2.out' });
      };
      anim.seleccionBoton = function (el) {
        gsap.fromTo(el, { scale: 0.94 }, { scale: 1, duration: 0.35, ease: 'back.out(2)' });
      };
      anim.dibujarCheck = function (path) {
        try {
          var largo = path.getTotalLength();
          path.style.strokeDasharray = largo;
          path.style.strokeDashoffset = largo;
          gsap.to(path, { strokeDashoffset: 0, duration: 0.3, ease: 'power1.out' });
        } catch (err) {
          path.style.strokeDashoffset = 0;
        }
      };
      anim.progreso = function (circulo, offset) {
        gsap.to(circulo, { strokeDashoffset: offset, duration: 0.4, ease: 'power3.out' });
      };
      anim.pulsoGuardar = function (boton) {
        if (!boton) return;
        var brillo = boton.querySelector('.brillo');
        var tl = gsap.timeline();
        tl.fromTo(boton, { scale: 1 }, { scale: 1.04, duration: 0.14, ease: 'power2.out', yoyo: true, repeat: 1 }, 0);
        if (brillo) {
          gsap.set(brillo, { xPercent: -150, skewX: -20 });
          tl.to(brillo, { xPercent: 350, duration: 0.6, ease: 'power1.inOut' }, 0);
        }
      };
      anim.abrirHoja = function (panel, fondo) {
        gsap.set(panel, { yPercent: 100 });
        gsap.set(fondo, { opacity: 0 });
        gsap.timeline()
          .to(fondo, { opacity: 1, duration: 0.25 }, 0)
          .to(panel, { yPercent: 0, duration: 0.45, ease: 'expo.out' }, 0);
      };
      anim.cerrarHoja = function (panel, fondo, onComplete) {
        gsap.timeline({ onComplete: onComplete })
          .to(panel, { yPercent: 100, duration: 0.3, ease: 'power2.in' }, 0)
          .to(fondo, { opacity: 0, duration: 0.25 }, 0);
      };
      anim.exito = function (refs) {
        gsap.set(refs.liquid, { transformOrigin: '50% 100%', scaleY: 0 });
        var tl = gsap.timeline();
        tl.to(refs.liquid, { scaleY: 1.05, duration: 0.35, ease: 'power2.out' }, 0.25)
          .to(refs.liquid, { scaleY: 1, duration: 0.2, ease: 'power1.inOut' }, 0.6);

        try {
          var largoOutline = refs.outline.getTotalLength();
          refs.outline.style.strokeDasharray = largoOutline;
          refs.outline.style.strokeDashoffset = largoOutline;
          var largoCheck = refs.check.getTotalLength();
          refs.check.style.strokeDasharray = largoCheck;
          refs.check.style.strokeDashoffset = largoCheck;
          tl.to(refs.outline, { strokeDashoffset: 0, duration: 0.35, ease: 'power1.out' }, 0)
            .to(refs.check, { strokeDashoffset: 0, duration: 0.3, ease: 'power1.out' }, 0.75);
        } catch (err) {
          refs.outline.style.strokeDashoffset = 0;
          refs.check.style.strokeDashoffset = 0;
        }
      };
    });

    mm.add('(prefers-reduced-motion: reduce)', function () {
      anim.entradaRevision = function (tarjetas) {
        gsap.fromTo(tarjetas, { opacity: 0 }, { opacity: 1, duration: 0.15 });
      };
      anim.seleccionBoton = function (el) { gsap.set(el, { scale: 1 }); };
      anim.dibujarCheck = function (path) { gsap.set(path, { strokeDashoffset: 0 }); };
      anim.progreso = function (circulo, offset) { gsap.set(circulo, { strokeDashoffset: offset }); };
      anim.pulsoGuardar = function () {};
      anim.abrirHoja = function (panel, fondo) { gsap.set(panel, { yPercent: 0 }); gsap.set(fondo, { opacity: 1 }); };
      anim.cerrarHoja = function (panel, fondo, onComplete) { onComplete(); };
      anim.exito = function (refs) {
        gsap.set(refs.outline, { strokeDashoffset: 0 });
        gsap.set(refs.check, { strokeDashoffset: 0 });
        gsap.set(refs.liquid, { transformOrigin: '50% 100%', scaleY: 1 });
        gsap.fromTo([refs.outline, refs.liquid, refs.check], { opacity: 0 }, { opacity: 1, duration: 0.15 });
      };
    });
  }

  function hoja(nombre) { return document.getElementById('hoja-' + nombre); }
  function abrirHojaAnimada(nombre) {
    var raiz = hoja(nombre);
    if (!raiz) return;
    anim.abrirHoja(raiz.querySelector('.panel'), raiz.querySelector('.fondo'));
  }
  function cerrarHojaAnimada(nombre, onComplete) {
    var raiz = hoja(nombre);
    if (!raiz) { onComplete(); return; }
    anim.cerrarHoja(raiz.querySelector('.panel'), raiz.querySelector('.fondo'), onComplete);
  }

  var CIRCUNFERENCIA_ANILLO = 2 * Math.PI * 18;

  // =====================================================================
  // Componente Alpine
  // =====================================================================
  document.addEventListener('alpine:init', function () {
    Alpine.data('bitacora', function () {
      return {
        pantalla: 'abrir', // 'selector-usuario' | 'abrir' | 'revision' | 'exito' | 'qr'
        usuario: null,
        colmenaId: null,
        colmenaInput: '',
        colmenaError: '',
        recientes: [],

        CAMPOS: Core.CAMPOS,
        tonoClases: TONO_CLASES,
        seleccion: {},

        ultimaCargando: false,
        ultima: null,

        guardando: false,
        modoDemo: !CFG.ENDPOINT,
        pendientes: [],
        mostrarResumen: false,
        mostrarPendientes: false,
        exitoInmediato: true,
        siguienteColmenaId: null,
        estadoEnvioTexto: '',

        qr: { prefijo: 'A', desde: 1, hasta: 24, padding: 2 },
        qrCeldas: [],

        get completosN() { return Core.completos(this.seleccion); },
        get totalCampos() { return Core.CAMPOS.length; },

        tiempoRelativo: tiempoRelativo,

        init: function () {
          var self = this;

          if (location.search.indexOf('vista=qr') !== -1) {
            this.pantalla = 'qr';
            this.generarQrs();
            return;
          }

          this.usuario = window.apiarioUsuarioActual ? window.apiarioUsuarioActual() : null;
          this.recientes = leerRecientes();
          this.refrescarPendientes();

          if (!this.usuario) {
            this.pantalla = 'selector-usuario';
          } else {
            this.irAColmenaDesdeUrl();
          }

          this.$watch('completosN', function (nuevo, anterior) {
            anim.progreso(document.getElementById('anillo-progreso-valor'), CIRCUNFERENCIA_ANILLO * (1 - nuevo / self.totalCampos));
            if (nuevo === self.totalCampos && anterior < self.totalCampos) {
              anim.pulsoGuardar(document.getElementById('btn-guardar'));
            }
          });

          window.addEventListener('online', function () { self.reintentarPendientes(); });
          setInterval(function () { if (self.pendientes.length) self.reintentarPendientes(); }, 30000);
          this.reintentarPendientes();
        },

        elegirUsuario: function (slug) {
          this.usuario = Object.assign({ slug: slug }, window.APIARIO_USUARIOS[slug]);
          actualizarParam('u', slug);
          storage.setItem(LS_USUARIO, slug);
          if (window.apiarioRenderChip) window.apiarioRenderChip();
          this.irAColmenaDesdeUrl();
        },

        irAColmenaDesdeUrl: function () {
          var params = new URLSearchParams(location.search);
          var id = Core.normalizarId(params.get('c') || '');
          if (id && Core.idValido(id)) {
            this.abrirColmena(id);
          } else {
            this.pantalla = 'abrir';
            var self = this;
            this.$nextTick(function () { self.$refs.inputColmena && self.$refs.inputColmena.focus(); });
          }
        },

        validarInputColmena: function () {
          var normalizado = Core.normalizarId(this.colmenaInput);
          this.colmenaError = (!normalizado || Core.idValido(normalizado))
            ? ''
            : 'ID inválido: letras, números y guiones, máx. 12 caracteres.';
        },

        confirmarColmenaInput: function () {
          var normalizado = Core.normalizarId(this.colmenaInput);
          if (!Core.idValido(normalizado)) {
            this.colmenaError = 'ID inválido: letras, números y guiones, máx. 12 caracteres.';
            return;
          }
          this.abrirColmena(normalizado);
        },

        abrirColmena: function (id) {
          var esCambio = this.pantalla === 'revision' && this.colmenaId && this.colmenaId !== id;
          this.colmenaId = id;
          this.colmenaInput = '';
          this.colmenaError = '';
          this.seleccion = {};
          this.ultima = null;
          this.recientes = agregarReciente(id);
          actualizarParam('c', id);
          this.pantalla = 'revision';
          this.cargarUltima();

          var self = this;
          this.$nextTick(function () {
            anim.entradaRevision(Array.prototype.slice.call(document.querySelectorAll('[data-tarjeta-campo]')));
            if (esCambio) {
              var idEl = document.getElementById('colmena-id-actual');
              if (idEl) anim.seleccionBoton(idEl);
            }
          });
        },

        otraColmena: function () {
          this.colmenaId = null;
          this.seleccion = {};
          actualizarParam('c', null);
          this.pantalla = 'abrir';
          var self = this;
          this.$nextTick(function () { self.$refs.inputColmena && self.$refs.inputColmena.focus(); });
        },

        cargarUltima: function () {
          var self = this;
          if (!CFG.ENDPOINT) { this.ultima = null; return; }
          this.ultimaCargando = true;
          var controlador = new AbortController();
          var vencido = setTimeout(function () { controlador.abort(); }, 6000);
          fetch(CFG.ENDPOINT + '?colmena=' + encodeURIComponent(this.colmenaId), { signal: controlador.signal })
            .then(function (r) { return r.json(); })
            .then(function (data) {
              self.ultima = (data && data.ok && data.revisiones && data.revisiones[0]) || null;
            })
            .catch(function () { self.ultima = null; })
            .finally(function () { clearTimeout(vencido); self.ultimaCargando = false; });
        },

        toneDe: function (campo, valor) {
          var opcion = campo.opciones.find(function (o) { return o.valor === valor; });
          return opcion ? this.tonoClases[opcion.tono] : 'bg-neutro text-white';
        },

        elegirOpcion: function (campoKey, valor, evento) {
          var teniaValorAntes = !!this.seleccion[campoKey];
          var yaElegida = this.seleccion[campoKey] === valor;
          this.seleccion[campoKey] = valor;
          if (yaElegida) return;

          if (navigator.vibrate) navigator.vibrate(10);
          anim.seleccionBoton(evento.currentTarget);

          if (!teniaValorAntes) {
            this.$nextTick(function () {
              requestAnimationFrame(function () {
                var check = document.querySelector('#tarjeta-campo-' + campoKey + ' .check-tarjeta');
                if (check) anim.dibujarCheck(check);
              });
            });
          }
          this.enfocarSiguientePendiente(campoKey);
        },

        enfocarSiguientePendiente: function (actual) {
          var idx = Core.CAMPOS.findIndex(function (c) { return c.key === actual; });
          var seleccion = this.seleccion;
          var siguiente = Core.CAMPOS.slice(idx + 1).find(function (c) { return !seleccion[c.key]; });
          if (!siguiente) return;
          var el = document.getElementById('tarjeta-campo-' + siguiente.key);
          if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        },

        manejarFlechas: function (evento) {
          var teclas = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -2, ArrowDown: 2 };
          if (!(evento.key in teclas)) return;
          evento.preventDefault();
          var botones = Array.prototype.slice.call(evento.currentTarget.querySelectorAll('[role="radio"]'));
          var actual = botones.indexOf(document.activeElement);
          if (actual === -1) actual = 0;
          var n = botones.length;
          var siguiente = ((actual + teclas[evento.key]) % n + n) % n;
          botones[siguiente].focus();
        },

        abrirResumen: function () {
          if (this.completosN < this.totalCampos) return;
          this.mostrarResumen = true;
          this.$nextTick(function () { abrirHojaAnimada('resumen'); });
        },
        cerrarResumen: function () {
          var self = this;
          cerrarHojaAnimada('resumen', function () { self.mostrarResumen = false; });
        },

        confirmarGuardado: function () {
          var self = this;
          cerrarHojaAnimada('resumen', function () { self.mostrarResumen = false; });
          this.guardando = true;
          this.estadoEnvioTexto = 'Guardando revisión…';

          var payload = Core.armarPayload({
            colmena: this.colmenaId,
            usuario: this.usuario ? this.usuario.slug : '',
            appVersion: CFG.APP_VERSION,
            seleccion: this.seleccion
          });
          outbox.agregar(payload);
          this.refrescarPendientes();
          this.enviarRegistro(payload, true);
        },

        enviarRegistro: function (payload, esIntentoInicial) {
          var self = this;

          function exito(inmediato) {
            outbox.quitar(payload.id);
            self.refrescarPendientes();
            if (esIntentoInicial) self.mostrarExito(inmediato);
          }

          if (!CFG.ENDPOINT) {
            setTimeout(function () { exito(true); }, 700);
            return;
          }

          fetch(CFG.ENDPOINT, { method: 'POST', body: JSON.stringify(payload), redirect: 'follow' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
              if (data && data.ok) { exito(true); return; }
              if (data && data.validacion) {
                outbox.marcarRechazado(payload.id, data.error || '');
                self.refrescarPendientes();
                self.estadoEnvioTexto = 'La revisión de ' + payload.colmena + ' fue rechazada: revisá los datos.';
              }
              // error genérico del backend: se deja pendiente, se reintenta solo
            })
            .catch(function () { /* sin red: sigue en la outbox, se reintenta solo */ });
        },

        mostrarExito: function (inmediato) {
          this.exitoInmediato = inmediato;
          this.estadoEnvioTexto = inmediato
            ? 'Revisión guardada.'
            : 'Revisión guardada en el dispositivo. Se enviará cuando haya señal.';
          this.siguienteColmenaId = Core.siguienteId(this.colmenaId);
          this.pantalla = 'exito';
          this.guardando = false;
          if (navigator.vibrate) navigator.vibrate([20, 40, 20]);
          this.$nextTick(function () {
            requestAnimationFrame(function () {
              anim.exito({
                outline: document.getElementById('hex-outline'),
                liquid: document.getElementById('hex-liquid'),
                check: document.getElementById('hex-check')
              });
            });
          });
        },

        siguienteColmena: function () {
          if (!this.siguienteColmenaId) return;
          this.abrirColmena(this.siguienteColmenaId);
        },

        refrescarPendientes: function () { this.pendientes = outbox.leer(); },

        reintentarPendientes: function () {
          var self = this;
          outbox.leer()
            .filter(function (r) { return r.estado !== 'rechazado'; })
            .forEach(function (registro) { self.enviarRegistro(registro, false); });
        },
        reintentarAhora: function () { this.reintentarPendientes(); },

        abrirPendientes: function () {
          this.mostrarPendientes = true;
          this.$nextTick(function () { abrirHojaAnimada('pendientes'); });
        },
        cerrarPendientes: function () {
          var self = this;
          cerrarHojaAnimada('pendientes', function () { self.mostrarPendientes = false; });
        },

        generarQrs: function () {
          var desde = Math.min(this.qr.desde, this.qr.hasta);
          var hasta = Math.max(this.qr.desde, this.qr.hasta);
          var prefijo = Core.normalizarId(this.qr.prefijo);
          var padding = Math.max(0, this.qr.padding | 0);
          var lista = [];
          for (var i = desde; i <= hasta; i++) {
            var id = prefijo + String(i).padStart(padding, '0');
            lista.push({ id: id, svg: svgQrPara(id) });
          }
          this.qrCeldas = lista;
        }
      };
    });
  });
})();
