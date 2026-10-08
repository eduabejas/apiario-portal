/**
 * Bitácora de colmenas (Interfaz 3): registro de revisiones desde el celular.
 * Store de Alpine, outbox offline, envío al Apps Script compartido con la
 * Interfaz 5 y animaciones GSAP. Reusa window.APIARIO_USUARIOS /
 * apiarioUsuarioActual (usuarios.js), window.apiarioRenderChip (topbar.js),
 * window.BitacoraCore (bitacora-core.js) y window.BITACORA_CFG
 * (bitacora-config.js, que toma la URL de bitacoraderevision/assets/config.js).
 */
(function () {
  "use strict";

  var Core = window.BitacoraCore;
  var CFG = window.BITACORA_CFG || { ENDPOINT: '', APP_VERSION: 'dev' };

  var LS_USUARIO = 'bitacora_usuario';
  var LS_RECIENTES = 'bitacora_colmenas_recientes';
  var LS_APIARIO = 'bitacora_apiario';
  var LS_CODIGO = 'bitacora_codigo';             // solo si se tilda «Recordar en este celular»
  var LS_ULTIMAS = 'bitacora_ultimas';           // última revisión por colmena (para ver sin señal)
  var LS_CODIGOS_MAPA = 'bitacora_codigos_mapa'; // colmenas y núcleos del mapa

  var TIEMPO_ENVIO = 15000;        // ms: pasado esto el envío queda en la outbox y se reintenta
  var TIEMPO_LECTURA = 10000;
  var REFRESCO_REVISIONES = 60000; // no volver a bajar la hoja más de una vez por minuto

  var TONO_CLASES = {
    ok: 'bg-ok text-white border-ok',
    medio: 'bg-medio text-tinta border-medio',
    alerta: 'bg-alerta text-white border-alerta',
    critico: 'bg-critico text-white border-critico',
    neutro: 'bg-neutro text-white border-neutro'
  };
  var ETIQUETA_VARROA = { ok: 'Normal', medio: 'Atención', critico: 'Alerta' };

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
        setItem: function (key, valor) { mem[key] = valor; },
        removeItem: function (key) { delete mem[key]; }
      };
    }
  }
  var storage = storageSeguro();
  var outbox = Core.crearOutbox(storage, 'bitacora_outbox');

  function leerJSON(key, porDefecto) {
    try {
      var crudo = storage.getItem(key);
      return crudo ? JSON.parse(crudo) : porDefecto;
    } catch (err) {
      return porDefecto;
    }
  }
  function escribirJSON(key, valor) {
    try { storage.setItem(key, JSON.stringify(valor)); } catch (err) { /* storage lleno: solo se pierde la copia offline */ }
  }

  // --- Código de acceso: en memoria; en el celular solo si se pide recordarlo.
  // Nunca viaja en la URL ni se guarda dentro de la outbox. ---
  var codigoMemoria = storage.getItem(LS_CODIGO) || '';
  function guardarCodigo(codigo, recordar) {
    codigoMemoria = codigo;
    if (recordar) storage.setItem(LS_CODIGO, codigo);
    else storage.removeItem(LS_CODIGO);
  }
  function olvidarCodigo() {
    codigoMemoria = '';
    storage.removeItem(LS_CODIGO);
  }

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
    return leerJSON(LS_RECIENTES, []);
  }
  function agregarReciente(id) {
    var lista = leerRecientes().filter(function (x) { return x !== id; });
    lista.unshift(id);
    lista = lista.slice(0, 6);
    escribirJSON(LS_RECIENTES, lista);
    return lista;
  }

  var MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
  function fechaBonita(iso) {
    var p = String(iso || '').split('-');
    if (p.length < 3) return String(iso || '');
    return parseInt(p[2], 10) + ' ' + MESES[parseInt(p[1], 10) - 1] + ' ' + p[0];
  }
  /** 'hoy', 'ayer' o 'hace N días' para una fecha 'AAAA-MM-DD'. */
  function cuandoFue(iso) {
    var p = String(iso || '').split('-');
    if (p.length < 3) return '';
    var dia = new Date(+p[0], +p[1] - 1, +p[2]);
    var hoy = new Date();
    hoy = new Date(hoy.getFullYear(), hoy.getMonth(), hoy.getDate());
    var dias = Math.round((hoy - dia) / 86400000);
    if (dias <= 0) return 'hoy';
    if (dias === 1) return 'ayer';
    return 'hace ' + dias + ' días';
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

  // --- Red ---
  function fetchJSON(url, opciones, ms) {
    var controlador = new AbortController();
    var vencido = setTimeout(function () { controlador.abort(); }, ms);
    return fetch(url, Object.assign({ signal: controlador.signal }, opciones || {}))
      .then(function (r) { return r.json(); })
      .finally(function () { clearTimeout(vencido); });
  }

  /**
   * Envía un registro de la outbox. POST "simple" (sin cabeceras extra) para
   * evitar el preflight CORS de Apps Script. → { resultado, motivo }
   */
  function postear(registro, codigo) {
    return fetchJSON(CFG.ENDPOINT, { method: 'POST', body: JSON.stringify({ codigo: codigo, datos: registro.datos }) }, TIEMPO_ENVIO)
      .then(function (res) {
        return { resultado: Core.clasificarRespuesta(res), motivo: (res && res.error) || '' };
      })
      .catch(function () { return { resultado: 'pendiente', motivo: 'sin señal' }; });
  }

  // Registros que ya están viajando: el reintento periódico no los duplica.
  var enVuelo = {};
  var enviandoCola = false;
  var ultimaCargaRevisiones = 0;
  // Lo guardado en esta sesión: se combina con la hoja por si la lectura
  // llega antes de que la fila nueva aparezca.
  var anotadasSesion = [];

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
        gsap.killTweensOf([panel, fondo]);
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
  // Turno por hoja: si se reabre mientras se está cerrando (p. ej. el servidor
  // contesta "código inválido" enseguida), el cierre viejo no la vuelve a ocultar.
  var turnoHoja = {};
  function nuevoTurnoHoja(nombre) {
    turnoHoja[nombre] = (turnoHoja[nombre] || 0) + 1;
    return turnoHoja[nombre];
  }
  function abrirHojaAnimada(nombre) {
    var raiz = hoja(nombre);
    if (!raiz) return;
    anim.abrirHoja(raiz.querySelector('.panel'), raiz.querySelector('.fondo'));
  }
  function cerrarHojaAnimada(nombre, onComplete) {
    var turno = nuevoTurnoHoja(nombre);
    var raiz = hoja(nombre);
    if (!raiz) { onComplete(); return; }
    anim.cerrarHoja(raiz.querySelector('.panel'), raiz.querySelector('.fondo'), function () {
      if (turnoHoja[nombre] === turno) onComplete();
    });
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
        codigosMapa: leerJSON(LS_CODIGOS_MAPA, []),

        CAMPOS: Core.CAMPOS,
        GRUPOS: Core.GRUPOS,
        ACARICIDAS: Core.ACARICIDAS,
        ACCIONES: Core.ACCIONES,
        tonoClases: TONO_CLASES,

        // Revisión en curso
        seleccion: {},
        hoy: Core.fechaISO(),
        fecha: Core.fechaISO(),
        fechaManual: false,
        apiario: storage.getItem(LS_APIARIO) || '',
        varroaTexto: '',
        acaricida: '',
        acaricidaOtro: false,
        acciones: [],
        observaciones: '',

        // Última revisión de cada colmena (copia local de la hoja)
        ultimas: leerJSON(LS_ULTIMAS, {}),
        revisionesCargando: false,

        enviando: false,
        errorEnvio: '',
        modoDemo: !CFG.ENDPOINT,
        pendientes: [],
        mostrarResumen: false,
        mostrarPendientes: false,
        exitoInmediato: true,
        siguienteColmenaId: null,
        estadoEnvioTexto: '',

        // Código de acceso (el valor real vive fuera del store, en codigoMemoria)
        tieneCodigo: !!codigoMemoria,
        necesitaCodigo: false,
        codigoInput: '',
        recordarCodigo: !!storage.getItem(LS_CODIGO),
        codigoRecordado: !!storage.getItem(LS_CODIGO),
        codigoError: '',

        qr: { prefijo: 'A', desde: 1, hasta: 24, padding: 2 },
        qrCeldas: [],

        get completosN() { return Core.completos(this.seleccion); },
        get totalCampos() { return Core.CAMPOS.length; },
        get varroa() {
          var v = Core.leerVarroa(this.varroaTexto);
          v.tono = v.valor === null ? '' : Core.tonoVarroa(v.valor);
          v.etiqueta = v.tono ? ETIQUETA_VARROA[v.tono] : '';
          return v;
        },
        get hayDatos() {
          return Core.hayDatos({
            seleccion: this.seleccion, varroa: this.varroaTexto, acaricida: this.acaricida,
            acciones: this.acciones, observaciones: this.observaciones
          });
        },
        get puedeGuardar() { return this.hayDatos && !this.varroa.error && !!this.fecha && !this.enviando; },
        get pideCodigo() { return !this.modoDemo && !this.tieneCodigo; },
        get ultima() { return (this.colmenaId && this.ultimas[this.colmenaId]) || null; },
        get pendientesEnviables() {
          return this.pendientes.filter(function (r) { return r.estado !== 'rechazado'; }).length;
        },
        get linkRegistros() {
          return 'bitacoraderevision/' + (this.usuario ? '?u=' + encodeURIComponent(this.usuario.slug) : '') + '#registros';
        },
        /** Lo cargado, en el orden del formulario, para la hoja de confirmación. */
        get resumenLista() {
          var self = this;
          var filas = [{ etiqueta: 'Fecha', valor: fechaBonita(this.fecha) + (this.fecha === this.hoy ? ' (hoy)' : '') }];
          if (this.apiario.trim()) filas.push({ etiqueta: 'Apiario', valor: this.apiario.trim() });
          Core.CAMPOS.forEach(function (c) {
            if (self.seleccion[c.key]) filas.push({ etiqueta: c.etiqueta, valor: self.seleccion[c.key] });
          });
          if (this.varroa.valor !== null) filas.push({ etiqueta: 'Varroa', valor: this.formatoPct(this.varroa.valor) });
          if (this.acaricida.trim()) filas.push({ etiqueta: 'Acaricida', valor: this.acaricida.trim() });
          if (this.acciones.length) filas.push({ etiqueta: 'Acciones', valor: this.accionesOrdenadas().join(', ') });
          if (this.observaciones.trim()) filas.push({ etiqueta: 'Observaciones', valor: this.observaciones.trim() });
          return filas;
        },

        tiempoRelativo: tiempoRelativo,
        fechaBonita: fechaBonita,
        cuandoFue: cuandoFue,
        formatoPct: function (n) { return n.toFixed(1).replace('.', ',') + ' %'; },

        init: function () {
          var self = this;

          if (location.search.indexOf('vista=qr') !== -1) {
            this.pantalla = 'qr';
            this.generarQrs();
            return;
          }

          this.usuario = window.apiarioUsuarioActual ? window.apiarioUsuarioActual() : null;
          this.recientes = leerRecientes();
          // Registros de la versión alpha (modo demo, otro formato): nunca se enviaron.
          outbox.leer().forEach(function (r) { if (!r.datos) outbox.quitar(r.id); });
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
          document.addEventListener('visibilitychange', function () {
            if (document.hidden) return;
            self.hoy = Core.fechaISO();
            if (!self.fechaManual) self.fecha = self.hoy;
            self.cargarRevisiones(false);
            self.reintentarPendientes();
          });
          setInterval(function () { if (self.pendientesEnviables) self.reintentarPendientes(); }, 30000);

          this.cargarRevisiones(true);
          this.cargarCodigosMapa();
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

        limpiarRevision: function () {
          this.seleccion = {};
          this.varroaTexto = '';
          this.acaricida = '';
          this.acaricidaOtro = false;
          this.acciones = [];
          this.observaciones = '';
          this.errorEnvio = '';
          this.hoy = Core.fechaISO();
          if (!this.fechaManual) this.fecha = this.hoy;
        },

        abrirColmena: function (id) {
          var esCambio = this.pantalla === 'revision' && this.colmenaId && this.colmenaId !== id;
          this.colmenaId = id;
          this.colmenaInput = '';
          this.colmenaError = '';
          this.limpiarRevision();
          this.recientes = agregarReciente(id);
          actualizarParam('c', id);
          this.pantalla = 'revision';
          this.cargarRevisiones(false);
          window.scrollTo(0, 0);

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
          this.limpiarRevision();
          actualizarParam('c', null);
          this.pantalla = 'abrir';
          var self = this;
          this.$nextTick(function () { self.$refs.inputColmena && self.$refs.inputColmena.focus(); });
        },

        // --- Datos compartidos con la Interfaz 5 (misma hoja) ---

        cargarRevisiones: function (forzar) {
          var self = this;
          if (this.modoDemo || this.revisionesCargando) return;
          if (!forzar && Date.now() - ultimaCargaRevisiones < REFRESCO_REVISIONES) return;
          this.revisionesCargando = true;
          fetchJSON(CFG.ENDPOINT, { method: 'GET' }, TIEMPO_LECTURA)
            .then(function (res) {
              if (!res || !res.ok || !Array.isArray(res.data)) return;
              ultimaCargaRevisiones = Date.now();
              self.ultimas = Core.ultimasPorColmena(res.data.concat(anotadasSesion));
              escribirJSON(LS_ULTIMAS, self.ultimas);
            })
            .catch(function () { /* sin señal: queda la copia local */ })
            .finally(function () { self.revisionesCargando = false; });
        },

        cargarCodigosMapa: function () {
          var self = this;
          if (this.modoDemo) return;
          fetchJSON(CFG.ENDPOINT + '?recurso=mapa', { method: 'GET' }, TIEMPO_LECTURA)
            .then(function (res) {
              // Un script sin mapa responde con las revisiones (sin `version`): no pisar la copia.
              if (!res || !res.ok || typeof res.version !== 'number') return;
              self.codigosMapa = Core.codigosDelMapa(res);
              escribirJSON(LS_CODIGOS_MAPA, self.codigosMapa);
            })
            .catch(function () { /* sin señal: queda la copia local */ });
        },

        /** Lo recién enviado pasa a ser la "última revisión" sin esperar a releer la hoja. */
        anotarUltima: function (registro) {
          var fila = Object.assign({ creado_en: new Date().toISOString() }, registro.datos);
          anotadasSesion.push(fila);
          var actual = this.ultimas[registro.colmena];
          var copia = Object.assign({}, this.ultimas);
          copia[registro.colmena] = actual ? Core.masReciente(actual, fila) : fila;
          this.ultimas = copia;
          escribirJSON(LS_ULTIMAS, this.ultimas);
        },

        revisadaHoy: function (id) {
          var hoy = this.hoy;
          var u = this.ultimas[id];
          if (u && u.fecha === hoy) return true;
          return this.pendientes.some(function (r) { return r.colmena === id && r.datos && r.datos.fecha === hoy; });
        },

        /** Chips de la última revisión: campos con valor, varroa y acaricida. */
        chipsDe: function (r) {
          if (!r) return [];
          var self = this;
          var chips = [];
          Core.CAMPOS.forEach(function (c) {
            if (r[c.key]) chips.push({ k: c.key, texto: c.corto + ': ' + r[c.key], clase: self.toneDe(c, r[c.key]) });
          });
          var v = Core.leerVarroa(r.varroa_pct);
          if (v.valor !== null) {
            chips.push({ k: 'varroa', texto: 'Varroa: ' + this.formatoPct(v.valor), clase: TONO_CLASES[Core.tonoVarroa(v.valor)] });
          }
          if (r.acaricida) chips.push({ k: 'acaricida', texto: 'Acaricida: ' + r.acaricida, clase: 'bg-white text-tinta border-borde' });
          return chips;
        },

        toneDe: function (campo, valor) {
          var opcion = campo.opciones.find(function (o) { return o.valor === valor; });
          return opcion ? this.tonoClases[opcion.tono] : 'bg-neutro text-white';
        },

        camposDe: function (grupo) {
          return Core.CAMPOS.filter(function (c) { return c.grupo === grupo; });
        },

        // --- Formulario ---

        elegirOpcion: function (campoKey, valor, evento) {
          var teniaValorAntes = !!this.seleccion[campoKey];
          if (this.seleccion[campoKey] === valor) return;
          this.seleccion[campoKey] = valor;

          if (navigator.vibrate) navigator.vibrate(10);
          anim.seleccionBoton(evento.currentTarget);

          if (!teniaValorAntes) {
            this.$nextTick(function () {
              requestAnimationFrame(function () {
                var check = document.querySelector('#tarjeta-campo-' + campoKey + ' .check-tarjeta');
                if (check) anim.dibujarCheck(check);
              });
            });
            this.enfocarSiguientePendiente(campoKey);
          }
        },

        /** Deja el campo sin dato (todos son opcionales). */
        quitarOpcion: function (campoKey) {
          this.seleccion[campoKey] = '';
        },

        enfocarSiguientePendiente: function (actual) {
          var idx = Core.CAMPOS.findIndex(function (c) { return c.key === actual; });
          var seleccion = this.seleccion;
          var siguiente = Core.CAMPOS.slice(idx + 1).find(function (c) { return !seleccion[c.key]; });
          var el = siguiente
            ? document.getElementById('tarjeta-campo-' + siguiente.key)
            : (Core.completos(seleccion) === Core.CAMPOS.length ? document.getElementById('seccion-varroa') : null);
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

        cambiarFecha: function () {
          this.fechaManual = !!this.fecha && this.fecha !== this.hoy;
        },
        guardarApiario: function () {
          storage.setItem(LS_APIARIO, this.apiario.trim());
        },

        /** Aplicar un acaricida implica "Trató varroa" (no se desmarca al sacarlo). */
        marcarTratoVarroa: function () {
          if (this.acciones.indexOf('Trató varroa') === -1) this.acciones.push('Trató varroa');
        },
        elegirAcaricida: function (nombre) {
          if (this.acaricida === nombre && !this.acaricidaOtro) {
            this.acaricida = '';
            return;
          }
          this.acaricidaOtro = false;
          this.acaricida = nombre;
          this.marcarTratoVarroa();
        },
        elegirAcaricidaOtro: function () {
          this.acaricida = '';
          this.acaricidaOtro = !this.acaricidaOtro;
          var self = this;
          if (this.acaricidaOtro) this.$nextTick(function () { self.$refs.acaricidaOtro && self.$refs.acaricidaOtro.focus(); });
        },
        escribirAcaricidaOtro: function () {
          if (this.acaricida.trim()) this.marcarTratoVarroa();
        },
        alternarAccion: function (accion) {
          var i = this.acciones.indexOf(accion);
          if (i === -1) this.acciones.push(accion); else this.acciones.splice(i, 1);
        },
        accionesOrdenadas: function () {
          var elegidas = this.acciones;
          return Core.ACCIONES.filter(function (a) { return elegidas.indexOf(a) !== -1; });
        },

        // --- Guardar ---

        abrirResumen: function () {
          if (!this.puedeGuardar) return;
          nuevoTurnoHoja('resumen');
          this.mostrarResumen = true;
          var self = this;
          this.$nextTick(function () {
            abrirHojaAnimada('resumen');
            if (self.pideCodigo && self.codigoError && self.$refs.codigoResumen) self.$refs.codigoResumen.focus();
          });
        },
        cerrarResumen: function () {
          var self = this;
          this.codigoError = '';
          cerrarHojaAnimada('resumen', function () { self.mostrarResumen = false; });
        },

        /** Toma el código escrito en una hoja; false si falta. */
        tomarCodigo: function () {
          if (!this.pideCodigo) return true;
          if (!this.codigoInput.trim()) {
            this.codigoError = 'Ingresá el código de acceso para poder guardar.';
            return false;
          }
          guardarCodigo(this.codigoInput, this.recordarCodigo);
          this.tieneCodigo = true;
          this.codigoRecordado = this.recordarCodigo;
          this.codigoInput = '';
          this.codigoError = '';
          return true;
        },

        confirmarGuardado: function () {
          var self = this;
          if (!this.puedeGuardar || !this.tomarCodigo()) return;
          cerrarHojaAnimada('resumen', function () { self.mostrarResumen = false; });
          this.enviando = true;
          this.errorEnvio = '';
          this.estadoEnvioTexto = 'Guardando revisión…';

          var payload = Core.armarPayload({
            colmena: this.colmenaId,
            usuario: this.usuario ? this.usuario.slug : '',
            registradoPor: this.usuario ? this.usuario.nombre : '',
            appVersion: CFG.APP_VERSION,
            fecha: this.fecha,
            apiario: this.apiario,
            seleccion: this.seleccion,
            varroa: this.varroaTexto,
            acaricida: this.acaricida,
            acciones: this.acciones,
            observaciones: this.observaciones
          });

          if (this.modoDemo) {
            setTimeout(function () { self.enviando = false; self.mostrarExito(true); }, 700);
            return;
          }

          outbox.agregar(payload);
          this.refrescarPendientes();
          enVuelo[payload.id] = true;
          postear(payload, codigoMemoria).then(function (r) {
            delete enVuelo[payload.id];
            self.enviando = false;
            if (r.resultado === 'ok') {
              outbox.quitar(payload.id);
              self.refrescarPendientes();
              self.anotarUltima(payload);
              self.mostrarExito(true);
              self.cargarRevisiones(true);
              return;
            }
            if (r.resultado === 'codigo' || r.resultado === 'rechazado') {
              // No se guardó: vuelve al formulario tal como estaba.
              outbox.quitar(payload.id);
              self.refrescarPendientes();
              if (r.resultado === 'codigo') {
                olvidarCodigo();
                self.tieneCodigo = false;
                self.codigoRecordado = false;
                self.codigoError = 'El código de acceso no es válido. Probá de nuevo.';
                self.estadoEnvioTexto = self.codigoError;
                self.abrirResumen();
              } else {
                self.errorEnvio = 'No se pudo guardar: ' + r.motivo;
                self.estadoEnvioTexto = self.errorEnvio;
              }
              return;
            }
            // Sin señal o error del servidor: queda en la outbox y se reintenta solo.
            self.mostrarExito(false);
          });
        },

        mostrarExito: function (inmediato) {
          this.exitoInmediato = inmediato;
          this.estadoEnvioTexto = inmediato
            ? 'Revisión guardada.'
            : 'Revisión guardada en el dispositivo. Se enviará cuando haya señal.';
          this.siguienteColmenaId = Core.siguienteColmena(this.colmenaId, this.codigosMapa);
          this.pantalla = 'exito';
          window.scrollTo(0, 0);
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

        // --- Outbox ---

        refrescarPendientes: function () { this.pendientes = outbox.leer(); },

        /** Manda la outbox de a un registro (el Apps Script escribe con lock). */
        reintentarPendientes: function () {
          var self = this;
          if (this.modoDemo || enviandoCola) return;
          var lista = outbox.leer().filter(function (r) { return r.estado !== 'rechazado' && r.datos && !enVuelo[r.id]; });
          if (!lista.length) { this.necesitaCodigo = false; return; }
          if (!codigoMemoria) { this.necesitaCodigo = true; return; }
          this.necesitaCodigo = false;
          enviandoCola = true;
          var huboEnvios = false;

          (function siguiente(i) {
            if (i >= lista.length) {
              enviandoCola = false;
              if (huboEnvios) self.cargarRevisiones(true);
              return;
            }
            var registro = lista[i];
            enVuelo[registro.id] = true;
            postear(registro, codigoMemoria).then(function (r) {
              delete enVuelo[registro.id];
              var seguir = true;
              if (r.resultado === 'ok') {
                outbox.quitar(registro.id);
                self.anotarUltima(registro);
                huboEnvios = true;
              } else if (r.resultado === 'rechazado') {
                outbox.marcarRechazado(registro.id, r.motivo);
                self.estadoEnvioTexto = 'La revisión de ' + registro.colmena + ' fue rechazada: ' + r.motivo;
              } else if (r.resultado === 'codigo') {
                olvidarCodigo();
                self.tieneCodigo = false;
                self.codigoRecordado = false;
                self.necesitaCodigo = true;
                seguir = false;
              } else {
                seguir = false; // sin señal: se reintenta en el próximo ciclo
              }
              self.refrescarPendientes();
              if (seguir) siguiente(i + 1);
              else { enviandoCola = false; if (huboEnvios) self.cargarRevisiones(true); }
            });
          })(0);
        },
        reintentarAhora: function () {
          if (!this.tomarCodigo()) return;
          this.reintentarPendientes();
        },
        olvidarCodigoGuardado: function () {
          olvidarCodigo();
          this.tieneCodigo = false;
          this.codigoRecordado = false;
          this.recordarCodigo = false;
          this.estadoEnvioTexto = 'Código de acceso olvidado en este celular.';
        },
        descartarPendiente: function (id) {
          outbox.quitar(id);
          this.refrescarPendientes();
        },

        abrirPendientes: function () {
          nuevoTurnoHoja('pendientes');
          this.mostrarPendientes = true;
          this.$nextTick(function () { abrirHojaAnimada('pendientes'); });
        },
        cerrarPendientes: function () {
          var self = this;
          this.codigoError = '';
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
