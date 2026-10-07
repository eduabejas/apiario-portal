/* ===========================================================================
   Bitácora de colmenas — pestaña «Mapa»
   Plano 2D en vista superior (SVG + JS nativo, sin librerías).
   Coordenadas en metros: x crece hacia el Este, y hacia el Sur (como SVG);
   el Norte siempre queda arriba. Rotación en grados, sentido horario.
   Se comunica con app.js solo a través de window.BITACORA y los eventos
   bitacora:revisiones / bitacora:tab.
   =========================================================================== */
(function () {
  'use strict';

  // ---- Constantes ----------------------------------------------------------
  const UMBRAL_VARROA = 3.0;            // %
  const GRILLA = 0.05;                  // m
  const PASO_ROT = 15;                  // °
  const IMAN = 0.15;                    // m
  const ZOOM_MIN = 10, ZOOM_MAX = 400;  // px por metro
  const MAX_HISTORIAL = 100;
  const LADO_MIN = 0.10, SEGMENTO_MIN = 0.20, LARGO_MAX = 50; // m
  const DISTANCIA_ASA_ROT = 24;         // px desde el lado -y local
  const ESCALA_CODIGOS = 45;            // px/m desde la que se muestran los códigos
  const ALTO_ETIQUETA = { S: 0.30, M: 0.50, L: 0.80 }; // m
  const LARGOS_ESCALA = [0.2, 0.5, 1, 2, 5, 10, 20];  // m
  const MARGEN_AJUSTE = { arriba: 64, abajo: 92, izq: 28, der: 64 }; // px libres al ajustar
  const TIPOS = {
    colmena:  { nombre: 'Colmena',  capa: 'capaColmenas', w: 0.41, h: 0.51 },
    nucleo:   { nombre: 'Núcleo',   capa: 'capaColmenas', w: 0.24, h: 0.51 },
    pallet:   { nombre: 'Pallet',   capa: 'capaBases',    w: 1.20, h: 1.20 },
    muro:     { nombre: 'Muro',     capa: 'capaLimites',  segmento: true, largo: 3 },
    valla:    { nombre: 'Valla',    capa: 'capaLimites',  segmento: true, largo: 3 },
    etiqueta: { nombre: 'Etiqueta', capa: 'capaTextos',   tam: 'M' }
  };

  // ---- Estado --------------------------------------------------------------
  const estado = {
    modo: 'ver',                      // 'ver' | 'editar'
    mapa: null,                       // documento vigente (copia de trabajo)
    versionBase: 0,                   // versión del servidor sobre la que se edita
    seleccion: null,                  // id | null
    vista: { tx: 0, ty: 0, s: 40 },   // translate (px) + escala (px/m)
    deshacer: [], rehacer: [],        // snapshots JSON (string) del arreglo items
    ultimoPaso: '[]',                 // snapshot del último paso confirmado
    revisionesPorCodigo: new Map(),   // códigoNormalizado -> revisiones (más reciente primero)
    cargado: false,
    cargando: false,
    edicionBloqueada: 'cargando',     // motivo por el que no se puede editar, o null
    ajustarPendiente: true
  };

  // ---- Contrato con app.js -------------------------------------------------
  const B = window.BITACORA = window.BITACORA || {};

  // ---- DOM -----------------------------------------------------------------
  const NS = 'http://www.w3.org/2000/svg';
  const $ = (id) => document.getElementById(id);
  const panel = $('panelMapa');
  const cont = $('mapaLienzo'); // no usar id="mapa": el hash #mapa haría saltar la página
  const svg = $('mapaSvg');
  const mundo = $('mundo');
  const capas = {
    capaLimites: $('capaLimites'),
    capaBases: $('capaBases'),
    capaColmenas: $('capaColmenas'),
    capaTextos: $('capaTextos')
  };
  const capaGrilla = $('capaGrilla');
  const capaSeleccion = $('capaSeleccion');
  const btnVer = $('mapaModoVer');
  const btnEditar = $('mapaModoEditar');
  const historial = $('mapaHistorial');
  const btnDeshacer = $('mapaDeshacer');
  const btnRehacer = $('mapaRehacer');
  const agregarCaja = $('mapaAgregarCaja');
  const btnAgregar = $('mapaAgregar');
  const menu = $('mapaMenu');
  const panelProp = $('mapaPanel');
  const campos = {
    codigo: $('mpCodigo'), texto: $('mpTexto'), alias: $('mpAlias'), reina: $('mpReina'),
    notas: $('mpNotas'), ancho: $('mpAncho'), largo: $('mpLargo'), largoSeg: $('mpLargoSegmento'),
    rot: $('mpRotacion'), piquera: $('mpPiquera'), tam: $('mpTamano')
  };
  const estadoEl = $('mapaEstado');
  const tooltip = $('mapaTooltip');
  const escalaSvg = $('mapaEscalaSvg');
  const escalaRegla = $('mapaEscalaRegla');
  const escalaTxt = $('mapaEscalaTxt');

  function el(tag, attrs, padre) {
    const n = document.createElementNS(NS, tag);
    if (attrs) attr(n, attrs);
    if (padre) padre.appendChild(n);
    return n;
  }
  function attr(n, attrs) {
    for (const k in attrs) n.setAttribute(k, attrs[k]);
  }
  const limitar = (v, a, b) => Math.min(b, Math.max(a, v));
  const normalizar = (s) => String(s == null ? '' : s).trim().toLowerCase();
  const esColmena = (it) => it.tipo === 'colmena' || it.tipo === 'nucleo';
  const coma = (n) => String(n).replace('.', ',');
  const redondear = (n) => Math.round(n * 1000) / 1000;
  /** Ajuste a la grilla de 0,05 m (con libre = true, solo redondea al mm). */
  const ajustarGrilla = (v, libre) => redondear(libre ? v : Math.round(v / GRILLA) * GRILLA);
  const normalizarAngulo = (a) => {
    const r = redondear(((a % 360) + 360) % 360);
    return r >= 360 ? 0 : r;
  };
  function nuevoId() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return 'id-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 10);
  }

  // =========================================================================
  //  Fechas y datos sanitarios
  // =========================================================================
  function fechaLocal(iso) {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(iso || ''));
    if (!m) return null;
    const f = new Date(+m[1], +m[2] - 1, +m[3]);
    return f.getMonth() === +m[2] - 1 ? f : null;
  }
  function hoyLocal() {
    const h = new Date();
    return new Date(h.getFullYear(), h.getMonth(), h.getDate());
  }
  function diasEntre(desde, hasta) {
    return Math.round((hasta - desde) / 864e5);
  }
  function plural(n, uno, varios) {
    return n + ' ' + (n === 1 ? uno : varios);
  }

  /** Edad de la reina en texto: «N días», «N meses» o «N año(s) M meses». */
  function edadReina(iso) {
    const f = fechaLocal(iso);
    const hoy = hoyLocal();
    if (!f || f > hoy) return '—';
    let meses = (hoy.getFullYear() - f.getFullYear()) * 12 + (hoy.getMonth() - f.getMonth());
    if (hoy.getDate() < f.getDate()) meses--;
    if (meses < 1) return plural(diasEntre(f, hoy), 'día', 'días');
    if (meses < 12) return plural(meses, 'mes', 'meses');
    const anios = Math.floor(meses / 12);
    const resto = meses % 12;
    return plural(anios, 'año', 'años') + (resto ? ' ' + plural(resto, 'mes', 'meses') : '');
  }

  function haceDias(dias) {
    if (dias == null || dias < 0) return '';
    if (dias === 0) return '(hoy)';
    return '(hace ' + plural(dias, 'día', 'días') + ')';
  }

  function numeroVarroa(v) {
    if (v === '' || v == null) return null;
    const n = Number(v);
    return isFinite(n) ? n : null;
  }

  function compararRecientes(a, b) {
    const fa = String(a.fecha || ''), fb = String(b.fecha || '');
    if (fa !== fb) return fa < fb ? 1 : -1;
    const ca = String(a.creado_en || ''), cb = String(b.creado_en || '');
    if (ca === cb) return 0;
    return ca < cb ? 1 : -1;
  }

  const cacheResumen = new Map();

  function indexarRevisiones(revs) {
    const indice = new Map();
    (Array.isArray(revs) ? revs : []).forEach((r) => {
      const clave = normalizar(r.numero_colmena);
      if (!clave) return;
      if (!indice.has(clave)) indice.set(clave, []);
      indice.get(clave).push(r);
    });
    indice.forEach((lista) => lista.sort(compararRecientes));
    estado.revisionesPorCodigo = indice;
    cacheResumen.clear();
    nodos.forEach((n) => { n.it = null; }); // fuerza a recalcular las alertas
    pedirRender();
    refrescarTooltip();
  }

  /**
   * Única fuente para tooltip y alerta roja de una colmena/núcleo:
   * { ultimaAcaricida: {fecha, producto, dias} | null, ultimoVarroa: {fecha, pct} | null, alerta }
   */
  function resumenSanitario(codigo) {
    const clave = normalizar(codigo);
    if (cacheResumen.has(clave)) return cacheResumen.get(clave);
    const lista = estado.revisionesPorCodigo.get(clave) || [];
    let ultimaAcaricida = null;
    let ultimoVarroa = null;
    for (let i = 0; i < lista.length && !(ultimaAcaricida && ultimoVarroa); i++) {
      const r = lista[i];
      if (!ultimaAcaricida) {
        const producto = String(r.acaricida == null ? '' : r.acaricida).trim();
        const trato = Array.isArray(r.acciones) && r.acciones.indexOf('Trató varroa') !== -1;
        if (producto || trato) {
          const f = fechaLocal(r.fecha);
          ultimaAcaricida = { fecha: r.fecha, producto: producto || 'Trató varroa', dias: f ? diasEntre(f, hoyLocal()) : null };
        }
      }
      if (!ultimoVarroa) {
        const pct = numeroVarroa(r.varroa_pct);
        if (pct !== null) ultimoVarroa = { fecha: r.fecha, pct: pct };
      }
    }
    const resumen = {
      ultimaAcaricida: ultimaAcaricida,
      ultimoVarroa: ultimoVarroa,
      alerta: !!ultimoVarroa && ultimoVarroa.pct >= UMBRAL_VARROA
    };
    cacheResumen.set(clave, resumen);
    return resumen;
  }

  // =========================================================================
  //  Geometría
  // =========================================================================
  const anchosTexto = new Map(); // `${tam}|${texto}` -> ancho medido en metros

  /** Ancho y alto locales (sin rotar) de un rectángulo o etiqueta, en metros. */
  function medidas(it) {
    if (it.tipo !== 'etiqueta') return [it.w, it.h];
    const alto = ALTO_ETIQUETA[it.tam] || ALTO_ETIQUETA.M;
    const medido = anchosTexto.get(it.tam + '|' + it.texto);
    const ancho = medido || String(it.texto || '').length * alto * 0.74;
    return [Math.max(ancho, alto), alto];
  }

  // Esquinas en el marco local: 0 = (-x,-y), 1 = (+x,-y), 2 = (+x,+y), 3 = (-x,+y).
  const SIGNOS_ESQUINA = [[-1, -1], [1, -1], [1, 1], [-1, 1]];

  function esquinas(it) {
    const m = medidas(it);
    const a = (it.rot || 0) * Math.PI / 180;
    const c = Math.cos(a), s = Math.sin(a);
    return SIGNOS_ESQUINA.map((k) => {
      const lx = k[0] * m[0] / 2, ly = k[1] * m[1] / 2;
      return [it.x + lx * c - ly * s, it.y + lx * s + ly * c];
    });
  }

  function puntosDeItem(it) {
    if (TIPOS[it.tipo].segmento) {
      const e = it.tipo === 'muro' ? 0.1 : 0;
      return [[it.x1 - e, it.y1 - e], [it.x1 + e, it.y1 + e], [it.x2 - e, it.y2 - e], [it.x2 + e, it.y2 + e]];
    }
    return esquinas(it);
  }

  function caja(puntos) {
    if (!puntos.length) return null;
    const c = { x1: Infinity, y1: Infinity, x2: -Infinity, y2: -Infinity };
    puntos.forEach((p) => {
      c.x1 = Math.min(c.x1, p[0]); c.y1 = Math.min(c.y1, p[1]);
      c.x2 = Math.max(c.x2, p[0]); c.y2 = Math.max(c.y2, p[1]);
    });
    return c;
  }

  function cajaDeItems(items) {
    let puntos = [];
    items.forEach((it) => { puntos = puntos.concat(puntosDeItem(it)); });
    return caja(puntos);
  }

  // =========================================================================
  //  Vista: pantalla <-> mundo, zoom y ajuste
  // =========================================================================
  function tamLienzo() {
    return { w: svg.clientWidth, h: svg.clientHeight };
  }
  function aPantalla(x, y) {
    const v = estado.vista;
    return [x * v.s + v.tx, y * v.s + v.ty];
  }
  function aMundo(px, py) {
    const v = estado.vista;
    return [(px - v.tx) / v.s, (py - v.ty) / v.s];
  }
  function zoomEn(px, py, factor) {
    const v = estado.vista;
    const s = limitar(v.s * factor, ZOOM_MIN, ZOOM_MAX);
    const w = aMundo(px, py);
    v.s = s;
    v.tx = px - w[0] * s;
    v.ty = py - w[1] * s;
    pedirRender();
  }
  function zoomCentro(factor) {
    const t = tamLienzo();
    zoomEn(t.w / 2, t.h / 2, factor);
  }
  function ajustar() {
    const t = tamLienzo();
    if (!t.w || !t.h) { estado.ajustarPendiente = true; return; }
    estado.ajustarPendiente = false;
    const v = estado.vista;
    const m = MARGEN_AJUSTE;
    const utilW = Math.max(t.w - m.izq - m.der, 40);
    const utilH = Math.max(t.h - m.arriba - m.abajo, 40);
    const c = cajaDeItems(estado.mapa ? estado.mapa.items : []);
    if (!c) {
      v.s = 40;
      v.tx = m.izq + utilW / 2;
      v.ty = m.arriba + utilH / 2;
    } else {
      // Al menos 4 m de contexto: una sola colmena no debe quedar enorme.
      const bw = Math.max(c.x2 - c.x1, 4), bh = Math.max(c.y2 - c.y1, 4);
      v.s = limitar(Math.min(utilW / bw, utilH / bh), ZOOM_MIN, ZOOM_MAX);
      v.tx = m.izq + utilW / 2 - (c.x1 + c.x2) / 2 * v.s;
      v.ty = m.arriba + utilH / 2 - (c.y1 + c.y2) / 2 * v.s;
    }
    pedirRender();
  }

  // =========================================================================
  //  Render (reconciliación por id; nunca innerHTML del SVG)
  // =========================================================================
  let renderPendiente = false;
  function pedirRender() {
    if (renderPendiente) return;
    renderPendiente = true;
    requestAnimationFrame(render);
  }

  function render() {
    renderPendiente = false;
    const t = tamLienzo();
    if (!t.w || !t.h) return; // pestaña oculta
    const v = estado.vista;
    mundo.setAttribute('transform', 'translate(' + v.tx + ' ' + v.ty + ') scale(' + v.s + ')');
    renderGrilla(t);
    renderItems();
    renderSeleccion();
    renderEscala();
  }

  const grillaFina = el('path', { class: 'g-fina' }, capaGrilla);
  const grillaFuerte = el('path', { class: 'g-fuerte' }, capaGrilla);

  function renderGrilla(t) {
    const v = estado.vista;
    const a = aMundo(0, 0), b = aMundo(t.w, t.h);
    const paso = v.s < 8 ? 5 : 1; // si 1 m mide menos de 8 px, solo las líneas de 5 m
    let fina = '', fuerte = '';
    for (let i = Math.ceil(a[0] / paso); i * paso <= b[0]; i++) {
      const px = Math.round(i * paso * v.s + v.tx) + 0.5;
      const d = 'M' + px + ' 0V' + t.h;
      if ((i * paso) % 5 === 0) fuerte += d; else fina += d;
    }
    for (let j = Math.ceil(a[1] / paso); j * paso <= b[1]; j++) {
      const py = Math.round(j * paso * v.s + v.ty) + 0.5;
      const d = 'M0 ' + py + 'H' + t.w;
      if ((j * paso) % 5 === 0) fuerte += d; else fina += d;
    }
    grillaFina.setAttribute('d', fina);
    grillaFuerte.setAttribute('d', fuerte);
  }

  const nodos = new Map(); // id -> { g, tipo, partes, it, s, alerta }

  function crearNodo(it) {
    const g = el('g', { class: 'it it-' + it.tipo, 'data-id': it.id });
    const p = {};
    if (TIPOS[it.tipo].segmento) {
      p.trazo = el('line', { class: 'trazo' }, g);
      if (it.tipo === 'valla') p.postes = el('g', { class: 'postes' }, g);
      p.golpe = el('line', { class: 'golpe-linea' }, g);
    } else {
      p.rot = el('g', null, g);
      if (it.tipo === 'etiqueta') {
        p.golpe = el('rect', { class: 'golpe' }, p.rot);
        p.texto = el('text', { class: 'texto' }, p.rot);
      } else {
        p.cuerpo = el('rect', { class: 'cuerpo' }, p.rot);
        if (it.tipo === 'pallet') {
          p.listones = [];
          for (let i = 0; i < 5; i++) p.listones.push(el('line', { class: 'liston' }, p.rot));
        } else {
          p.piquera = el('rect', { class: 'piquera' }, p.rot);
          p.codigo = el('text', { class: 'codigo-it' }, g);
          p.punto = el('circle', { class: 'alerta-punto' }, g);
        }
      }
    }
    return { g: g, tipo: it.tipo, partes: p, it: null, s: 0, alerta: false };
  }

  function etiquetaAccesible(it) {
    const tipo = TIPOS[it.tipo].nombre;
    if (esColmena(it)) return tipo + ' ' + it.codigo + (it.alias ? ', ' + it.alias : '');
    if (it.tipo === 'etiqueta') return tipo + ' ' + it.texto;
    return tipo + (it.alias ? ', ' + it.alias : '');
  }

  function actualizarNodo(n, it, s, alerta) {
    n.it = it;
    n.s = s;
    n.alerta = alerta;
    const p = n.partes;
    n.g.classList.toggle('alerta', alerta);
    // En modo Editar cada elemento se alcanza con Tab y se selecciona con Enter.
    if (estado.modo === 'editar') {
      attr(n.g, { tabindex: '0', role: 'button', 'aria-label': etiquetaAccesible(it) });
    } else {
      n.g.removeAttribute('tabindex');
      n.g.removeAttribute('role');
      n.g.removeAttribute('aria-label');
    }

    if (TIPOS[it.tipo].segmento) {
      const linea = { x1: it.x1, y1: it.y1, x2: it.x2, y2: it.y2 };
      attr(p.trazo, linea);
      attr(p.golpe, linea);
      if (p.postes) renderPostes(p.postes, it, s);
      return;
    }

    n.g.setAttribute('transform', 'translate(' + it.x + ' ' + it.y + ')');
    p.rot.setAttribute('transform', 'rotate(' + (it.rot || 0) + ')');

    if (it.tipo === 'etiqueta') {
      const alto = ALTO_ETIQUETA[it.tam] || ALTO_ETIQUETA.M;
      p.texto.setAttribute('font-size', alto);
      p.texto.textContent = String(it.texto || '').toUpperCase();
      const clave = it.tam + '|' + it.texto;
      if (!anchosTexto.has(clave)) {
        const ancho = p.texto.getComputedTextLength();
        if (ancho > 0) anchosTexto.set(clave, ancho);
      }
      const m = medidas(it);
      attr(p.golpe, { x: -m[0] / 2, y: -m[1] / 2, width: m[0], height: m[1] });
      return;
    }

    attr(p.cuerpo, { x: -it.w / 2, y: -it.h / 2, width: it.w, height: it.h });

    if (it.tipo === 'pallet') {
      // 5 listones paralelos al lado largo.
      const largoEnX = it.w >= it.h;
      p.listones.forEach((l, i) => {
        const f = (i + 1) / 6;
        if (largoEnX) attr(l, { x1: -it.w / 2, x2: it.w / 2, y1: -it.h / 2 + it.h * f, y2: -it.h / 2 + it.h * f });
        else attr(l, { y1: -it.h / 2, y2: it.h / 2, x1: -it.w / 2 + it.w * f, x2: -it.w / 2 + it.w * f });
      });
      return;
    }

    // Colmena / núcleo: piquera (2 px de alto, 60 % del ancho) sobre el lado +y local.
    attr(p.piquera, { x: -it.w * 0.3, y: it.h / 2 + 0.6 / s, width: it.w * 0.6, height: 2 / s });

    const verCodigo = s >= ESCALA_CODIGOS;
    p.codigo.style.display = verCodigo ? '' : 'none';
    if (verCodigo) {
      p.codigo.setAttribute('font-size', limitar(0.22 * s, 9, 11) / s);
      p.codigo.textContent = it.codigo;
    }

    p.punto.style.display = alerta ? '' : 'none';
    if (alerta) {
      // Esquina noreste: la más al Este y al Norte (x grande, y chica).
      let ne = null;
      esquinas(it).forEach((e) => { if (!ne || e[0] - e[1] > ne[0] - ne[1]) ne = e; });
      attr(p.punto, { cx: ne[0] - it.x, cy: ne[1] - it.y, r: 2.5 / s });
    }
  }

  function renderPostes(grupo, it, s) {
    while (grupo.firstChild) grupo.removeChild(grupo.firstChild);
    const dx = it.x2 - it.x1, dy = it.y2 - it.y1;
    const largo = Math.hypot(dx, dy);
    const cuantos = Math.floor(largo / 1.5 + 1e-9);
    const pos = [];
    for (let k = 0; k <= cuantos; k++) pos.push(largo ? (k * 1.5) / largo : 0);
    if (pos[pos.length - 1] < 1 - 1e-6) pos.push(1);
    pos.forEach((f) => el('circle', { class: 'poste', cx: it.x1 + dx * f, cy: it.y1 + dy * f, r: 2 / s }, grupo));
  }

  function renderItems() {
    const items = estado.mapa ? estado.mapa.items : [];
    const s = estado.vista.s;
    const vivos = new Set();
    items.forEach((it) => {
      vivos.add(it.id);
      let n = nodos.get(it.id);
      if (n && n.tipo !== it.tipo) { n.g.remove(); n = null; }
      if (!n) { n = crearNodo(it); nodos.set(it.id, n); }
      const alerta = esColmena(it) && resumenSanitario(it.codigo).alerta;
      if (n.it === it && n.s === s && n.alerta === alerta) return;
      // Las etiquetas se miden después de estar en el documento.
      if (!n.g.parentNode) capas[TIPOS[it.tipo].capa].appendChild(n.g);
      actualizarNodo(n, it, s, alerta);
    });
    nodos.forEach((n, id) => {
      if (!vivos.has(id)) { n.g.remove(); nodos.delete(id); }
    });
    ordenarCapas(items);
  }

  /** Orden fijo por capa y, dentro de la capa, por orden en items. */
  function ordenarCapas(items) {
    const porCapa = {};
    items.forEach((it) => {
      const nombre = TIPOS[it.tipo].capa;
      (porCapa[nombre] = porCapa[nombre] || []).push(nodos.get(it.id).g);
    });
    Object.keys(capas).forEach((nombre) => {
      const esperados = porCapa[nombre] || [];
      const actuales = capas[nombre].children;
      let igual = actuales.length === esperados.length;
      for (let i = 0; igual && i < esperados.length; i++) if (actuales[i] !== esperados[i]) igual = false;
      if (!igual) esperados.forEach((g) => capas[nombre].appendChild(g));
    });
  }

  let escalaS = 0;
  function renderEscala() {
    const s = estado.vista.s;
    if (s === escalaS) return;
    escalaS = s;
    let mejor = LARGOS_ESCALA[0], distancia = Infinity;
    for (let i = 0; i < LARGOS_ESCALA.length; i++) {
      const px = LARGOS_ESCALA[i] * s;
      const d = px < 60 ? 60 - px : (px > 120 ? px - 120 : 0);
      if (d < distancia) { distancia = d; mejor = LARGOS_ESCALA[i]; }
      if (d === 0) break;
    }
    const px = Math.round(mejor * s);
    const fin = px + 1, medio = Math.round(px / 2) + 1;
    escalaSvg.setAttribute('width', px + 2);
    escalaRegla.setAttribute('d', 'M1 2V11M1 11H' + fin + 'M' + fin + ' 2V11M' + medio + ' 6V11');
    escalaTxt.textContent = coma(mejor) + ' m';
  }

  // ---- Selección y asas (en coordenadas de pantalla) ------------------------
  const punteroGrueso = window.matchMedia('(pointer: coarse)');
  const radioAsa = () => (punteroGrueso.matches ? 11 : 5);

  /** Dirección (en el mundo) del lado -y local: opuesto a la piquera. */
  function direccionFrente(it) {
    const a = (it.rot || 0) * Math.PI / 180;
    return [Math.sin(a), -Math.cos(a)];
  }

  /**
   * Medias medidas en px para ubicar las asas: si el elemento es chico en
   * pantalla, las asas se separan hacia afuera para no encimarse.
   */
  function mediasAsas(it) {
    const m = medidas(it), s = estado.vista.s, minimo = radioAsa() + 3;
    return [Math.max(m[0] * s / 2, minimo), Math.max(m[1] * s / 2, minimo)];
  }

  /** Punto de pantalla a (lx, ly) px del centro, en el marco local rotado. */
  function desdeCentro(it, lx, ly) {
    const c = aPantalla(it.x, it.y);
    const a = (it.rot || 0) * Math.PI / 180, cos = Math.cos(a), sin = Math.sin(a);
    return [c[0] + lx * cos - ly * sin, c[1] + lx * sin + ly * cos];
  }

  /** Posición en pantalla del asa de rotación (a 24 px del lado -y local). */
  function posAsaRot(it) {
    const mh = mediasAsas(it)[1];
    const borde = it.tipo === 'etiqueta' ? medidas(it)[1] * estado.vista.s / 2 : mh;
    return { borde: desdeCentro(it, 0, -borde), asa: desdeCentro(it, 0, -(borde + DISTANCIA_ASA_ROT)) };
  }

  function renderSeleccion() {
    while (capaSeleccion.firstChild) capaSeleccion.removeChild(capaSeleccion.firstChild);
    if (estado.modo !== 'editar' || !estado.seleccion) return;
    const it = itemPorId(estado.seleccion);
    if (!it) return;
    const r = radioAsa();
    if (TIPOS[it.tipo].segmento) {
      const a = aPantalla(it.x1, it.y1), b = aPantalla(it.x2, it.y2);
      const largo = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
      const media = it.tipo === 'muro' ? 0.1 * estado.vista.s : 0;
      const off = media + 6;
      const nx = -(b[1] - a[1]) / largo * off, ny = (b[0] - a[0]) / largo * off;
      el('polygon', { class: 'sel-contorno', points: [[a[0] + nx, a[1] + ny], [b[0] + nx, b[1] + ny], [b[0] - nx, b[1] - ny], [a[0] - nx, a[1] - ny]].join(' ') }, capaSeleccion);
      el('circle', { class: 'asa', 'data-asa': 'p1', cx: a[0], cy: a[1], r: r }, capaSeleccion);
      el('circle', { class: 'asa', 'data-asa': 'p2', cx: b[0], cy: b[1], r: r }, capaSeleccion);
      return;
    }
    const pantalla = esquinas(it).map((p) => aPantalla(p[0], p[1]));
    el('polygon', { class: 'sel-contorno', points: pantalla.join(' ') }, capaSeleccion);
    const rot = posAsaRot(it);
    el('line', { class: 'sel-rot-linea', x1: rot.borde[0], y1: rot.borde[1], x2: rot.asa[0], y2: rot.asa[1] }, capaSeleccion);
    if (it.tipo !== 'etiqueta') {
      const medias = mediasAsas(it);
      SIGNOS_ESQUINA.forEach((sg, i) => {
        const p = desdeCentro(it, sg[0] * medias[0], sg[1] * medias[1]);
        el('circle', { class: 'asa', 'data-asa': String(i), cx: p[0], cy: p[1], r: r }, capaSeleccion);
      });
    }
    el('circle', { class: 'asa asa-rot', 'data-asa': 'rot', cx: rot.asa[0], cy: rot.asa[1], r: r + 1 }, capaSeleccion);
  }

  // =========================================================================
  //  Edición
  // =========================================================================
  function items() {
    return estado.mapa ? estado.mapa.items : [];
  }
  function ponerItems(lista) {
    estado.mapa = { esquema: 1, unidad: 'm', items: lista };
  }
  function reemplazarItem(nuevo) {
    ponerItems(items().map((it) => (it.id === nuevo.id ? nuevo : it)));
    pedirRender();
  }
  const limitarCoord = (v) => limitar(v, -1000, 1000);

  /** Extremos de muros y vallas (salvo los del elemento `excluirId`). */
  function extremosDeSegmentos(excluirId) {
    const lista = [];
    items().forEach((it) => {
      if (!TIPOS[it.tipo].segmento || it.id === excluirId) return;
      lista.push([it.x1, it.y1], [it.x2, it.y2]);
    });
    return lista;
  }

  /** Extremo más cercano a ≤ IMAN de `p`, o null. */
  function iman(p, excluirId) {
    let mejor = null, distancia = IMAN + 1e-9;
    extremosDeSegmentos(excluirId).forEach((e) => {
      const d = Math.hypot(e[0] - p[0], e[1] - p[1]);
      if (d <= distancia) { distancia = d; mejor = e; }
    });
    return mejor;
  }

  function moverItem(orig, dx, dy, libre) {
    if (!TIPOS[orig.tipo].segmento) {
      return Object.assign({}, orig, {
        x: limitarCoord(ajustarGrilla(orig.x + dx, libre)),
        y: limitarCoord(ajustarGrilla(orig.y + dy, libre))
      });
    }
    const vx = orig.x2 - orig.x1, vy = orig.y2 - orig.y1;
    let x1 = ajustarGrilla(orig.x1 + dx, libre), y1 = ajustarGrilla(orig.y1 + dy, libre);
    if (!libre) {
      // Si algún extremo queda cerca de otro muro/valla, se pega todo el segmento.
      const extremos = [[x1, y1], [x1 + vx, y1 + vy]];
      let mejor = null;
      extremos.forEach((e) => {
        const destino = iman(e, orig.id);
        if (destino) {
          const d = Math.hypot(destino[0] - e[0], destino[1] - e[1]);
          if (!mejor || d < mejor.d) mejor = { d: d, dx: destino[0] - e[0], dy: destino[1] - e[1] };
        }
      });
      if (mejor) { x1 += mejor.dx; y1 += mejor.dy; }
    }
    return Object.assign({}, orig, {
      x1: limitarCoord(redondear(x1)), y1: limitarCoord(redondear(y1)),
      x2: limitarCoord(redondear(x1 + vx)), y2: limitarCoord(redondear(y1 + vy))
    });
  }

  /** Punto del mundo que arrastra cada asa (esquina real o extremo). */
  function anclaDeAsa(it, asa) {
    if (asa === 'p1') return [it.x1, it.y1];
    if (asa === 'p2') return [it.x2, it.y2];
    if (asa === 'rot') return null;
    return esquinas(it)[Number(asa)];
  }

  /** Aplica el arrastre de un asa (esquina 0–3, extremo p1/p2 o rotación). */
  function aplicarAsa(orig, asa, w, libre) {
    if (asa === 'rot') {
      const grados = Math.atan2(w[0] - orig.x, -(w[1] - orig.y)) * 180 / Math.PI;
      return Object.assign({}, orig, { rot: normalizarAngulo(libre ? grados : Math.round(grados / PASO_ROT) * PASO_ROT) });
    }
    if (asa === 'p1' || asa === 'p2') {
      const fijo = asa === 'p1' ? [orig.x2, orig.y2] : [orig.x1, orig.y1];
      let p = [ajustarGrilla(w[0], libre), ajustarGrilla(w[1], libre)];
      if (!libre) {
        const destino = iman(p, orig.id);
        if (destino) p = destino.slice();
      }
      let dx = p[0] - fijo[0], dy = p[1] - fijo[1];
      const largo = Math.hypot(dx, dy);
      if (largo < SEGMENTO_MIN || largo > LARGO_MAX) {
        const previo = asa === 'p1' ? [orig.x1 - fijo[0], orig.y1 - fijo[1]] : [orig.x2 - fijo[0], orig.y2 - fijo[1]];
        const base = largo > 1e-9 ? [dx / largo, dy / largo] : [previo[0] / (Math.hypot(previo[0], previo[1]) || 1), previo[1] / (Math.hypot(previo[0], previo[1]) || 1)];
        const nuevo = limitar(largo, SEGMENTO_MIN, LARGO_MAX);
        dx = base[0] * nuevo; dy = base[1] * nuevo;
      }
      const punto = [limitarCoord(redondear(fijo[0] + dx)), limitarCoord(redondear(fijo[1] + dy))];
      return Object.assign({}, orig, asa === 'p1' ? { x1: punto[0], y1: punto[1] } : { x2: punto[0], y2: punto[1] });
    }
    // Esquina de un rectángulo: la esquina opuesta queda fija.
    const i = Number(asa);
    const signo = SIGNOS_ESQUINA[i];
    const fija = esquinas(orig)[(i + 2) % 4];
    const a = (orig.rot || 0) * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
    const rx = w[0] - fija[0], ry = w[1] - fija[1];
    const lx = rx * c + ry * s, ly = -rx * s + ry * c; // al marco local
    const lado = (v) => limitar(libre ? redondear(v) : redondear(Math.round(v / GRILLA) * GRILLA), LADO_MIN, LARGO_MAX);
    const ancho = lado(lx * signo[0]), alto = lado(ly * signo[1]);
    const cx = signo[0] * ancho / 2, cy = signo[1] * alto / 2;
    return Object.assign({}, orig, {
      w: ancho, h: alto,
      x: limitarCoord(redondear(fija[0] + cx * c - cy * s)),
      y: limitarCoord(redondear(fija[1] + cx * s + cy * c))
    });
  }

  /** Código automático: C-01, C-02… / N-01… (el siguiente al mayor usado). */
  function siguienteCodigo(tipo) {
    const prefijo = tipo === 'nucleo' ? 'N-' : 'C-';
    const patron = new RegExp('^' + prefijo + '(\\d+)$', 'i');
    let mayor = 0;
    items().forEach((it) => {
      const m = esColmena(it) && patron.exec(String(it.codigo).trim());
      if (m) mayor = Math.max(mayor, parseInt(m[1], 10));
    });
    return prefijo + String(mayor + 1).padStart(2, '0');
  }

  function crear(tipo) {
    const t = tamLienzo();
    const centro = aMundo(t.w / 2, t.h / 2);
    const cx = limitarCoord(ajustarGrilla(centro[0])), cy = limitarCoord(ajustarGrilla(centro[1]));
    const d = TIPOS[tipo];
    const it = { id: nuevoId(), tipo: tipo };
    if (d.segmento) {
      Object.assign(it, { x1: redondear(cx - d.largo / 2), y1: cy, x2: redondear(cx + d.largo / 2), y2: cy, alias: '' });
    } else if (tipo === 'etiqueta') {
      Object.assign(it, { x: cx, y: cy, rot: 0, texto: 'Etiqueta', tam: d.tam });
    } else {
      Object.assign(it, { x: cx, y: cy, w: d.w, h: d.h, rot: 0 });
      if (esColmena(it)) Object.assign(it, { codigo: siguienteCodigo(tipo), alias: '', reina_fecha: '', notas: '' });
      else it.alias = '';
    }
    ponerItems(items().concat([it]));
    seleccionar(it.id);
    asegurarVisible();
    confirmarPaso();
    actualizarEstadoVacio();
    if (tipo === 'etiqueta' && !punteroGrueso.matches) {
      campos.texto.focus();
      campos.texto.select();
    }
  }

  function duplicar(id) {
    const lista = items();
    const idx = lista.findIndex((it) => it.id === id);
    if (idx === -1) return;
    const copia = moverItem(Object.assign({}, lista[idx], { id: nuevoId() }), 0.5, 0.5, true);
    if (esColmena(copia)) copia.codigo = siguienteCodigo(copia.tipo);
    ponerItems(lista.slice(0, idx + 1).concat([copia], lista.slice(idx + 1)));
    seleccionar(copia.id);
    asegurarVisible();
    confirmarPaso();
  }

  function borrar(id) {
    ponerItems(items().filter((it) => it.id !== id));
    if (tooltipId === id) ocultarTooltip();
    deseleccionar();
    confirmarPaso();
    actualizarEstadoVacio();
  }

  function empujar(dx, dy) {
    const it = itemPorId(estado.seleccion);
    if (!it) return;
    reemplazarItem(moverItem(it, dx, dy, true));
    confirmarPaso();
    sincronizarPanel();
  }

  function seleccionar(id) {
    estado.seleccion = id;
    sincronizarPanel();
    pedirRender();
  }

  function deseleccionar() {
    if (!estado.seleccion) return;
    estado.seleccion = null;
    sincronizarPanel();
    pedirRender();
  }

  /**
   * Si el panel de propiedades tapa la selección, corre la vista: hacia arriba
   * cuando es hoja inferior (móvil) y hacia la izquierda cuando es overlay.
   */
  function asegurarVisible() {
    const it = itemPorId(estado.seleccion);
    if (!it || panelProp.hidden) return;
    requestAnimationFrame(() => {
      const actual = itemPorId(estado.seleccion);
      if (!actual) return;
      const c = caja(puntosDeItem(actual).map((p) => aPantalla(p[0], p[1])));
      const margen = 16;
      if (window.innerWidth < 640) {
        const limite = cont.clientHeight - panelProp.offsetHeight - margen;
        if (c.y2 > limite) estado.vista.ty -= c.y2 - limite;
      } else {
        const limite = panelProp.offsetLeft - margen;
        if (c.x2 > limite && c.y1 < panelProp.offsetTop + panelProp.offsetHeight) estado.vista.tx -= c.x2 - limite;
      }
      pedirRender();
    });
  }

  // ---- Deshacer / rehacer (snapshot al terminar cada gesto) ---------------
  function snapshot() {
    return JSON.stringify(items());
  }
  function reiniciarHistorial() {
    estado.deshacer = [];
    estado.rehacer = [];
    estado.ultimoPaso = snapshot();
    actualizarBotonesHistorial();
  }
  function confirmarPaso() {
    const actual = snapshot();
    if (actual === estado.ultimoPaso) return;
    estado.deshacer.push(estado.ultimoPaso);
    if (estado.deshacer.length > MAX_HISTORIAL) estado.deshacer.shift();
    estado.rehacer = [];
    estado.ultimoPaso = actual;
    actualizarBotonesHistorial();
  }
  function restaurar(snap) {
    estado.ultimoPaso = snap;
    ponerItems(JSON.parse(snap));
    if (estado.seleccion && !itemPorId(estado.seleccion)) estado.seleccion = null;
    if (tooltipId && !itemPorId(tooltipId)) ocultarTooltip();
    sincronizarPanel();
    actualizarBotonesHistorial();
    actualizarEstadoVacio();
    pedirRender();
  }
  function deshacer() {
    if (!estado.deshacer.length) return;
    estado.rehacer.push(estado.ultimoPaso);
    restaurar(estado.deshacer.pop());
  }
  function rehacer() {
    if (!estado.rehacer.length) return;
    estado.deshacer.push(estado.ultimoPaso);
    restaurar(estado.rehacer.pop());
  }
  function actualizarBotonesHistorial() {
    btnDeshacer.disabled = !estado.deshacer.length;
    btnRehacer.disabled = !estado.rehacer.length;
  }

  // =========================================================================
  //  Tooltip
  // =========================================================================
  let tooltipId = null;       // id del elemento mostrado
  let tooltipAnclado = false; // táctil: anclado sobre el elemento
  let tooltipTimer = 0;
  let ultimoPuntero = null;

  function itemPorId(id) {
    const items = estado.mapa ? estado.mapa.items : [];
    for (let i = 0; i < items.length; i++) if (items[i].id === id) return items[i];
    return null;
  }

  function nodoTexto(tag, clase, texto) {
    const n = document.createElement(tag);
    if (clase) n.className = clase;
    if (texto != null) n.textContent = texto;
    return n;
  }

  /** Fila etiqueta / valor; `segunda` es una línea extra bajo el valor (nodo). */
  function fila(destino, etiqueta, principal, segunda, claseValor) {
    destino.appendChild(nodoTexto('span', 'tt-k', etiqueta));
    const v = nodoTexto('span', 'tt-v' + (claseValor ? ' ' + claseValor : ''), principal);
    if (segunda) v.appendChild(segunda);
    destino.appendChild(v);
  }

  /** Arma el contenido del tooltip, o devuelve false si ese elemento no lleva. */
  function armarTooltip(it) {
    const fecha = B.fechaBonita || ((f) => f);
    tooltip.textContent = '';
    const tipo = TIPOS[it.tipo].nombre;
    if (!esColmena(it)) {
      if (!it.alias) return false;
      tooltip.appendChild(nodoTexto('div', 'tt-tipo', tipo));
      tooltip.appendChild(nodoTexto('div', 'tt-alias', it.alias));
      return true;
    }
    tooltip.appendChild(nodoTexto('div', 'tt-tipo', tipo + ' · ' + it.codigo));
    tooltip.appendChild(it.alias
      ? nodoTexto('div', 'tt-alias', '«' + it.alias + '»')
      : nodoTexto('div', 'tt-alias vacio', 'Sin alias'));

    const r = resumenSanitario(it.codigo);
    const filas = nodoTexto('div', 'tt-filas');
    fila(filas, 'Edad de la reina', edadReina(it.reina_fecha));
    if (r.ultimaAcaricida) {
      const a = r.ultimaAcaricida;
      const linea = nodoTexto('span', 'tt-linea', a.producto);
      const hace = haceDias(a.dias);
      if (hace) linea.appendChild(nodoTexto('span', 'tt-gris', ' ' + hace));
      fila(filas, 'Última acaricida', fecha(a.fecha), linea);
    } else {
      fila(filas, 'Última acaricida', 'Sin registro', null, 'tt-gris');
    }
    if (r.ultimoVarroa) {
      const u = r.ultimoVarroa;
      const pct = nodoTexto('span', 'tt-linea' + (r.alerta ? ' tt-alerta' : ''), u.pct.toFixed(1).replace('.', ',') + ' %');
      fila(filas, 'Último varroa', fecha(u.fecha), pct);
    } else {
      fila(filas, 'Último varroa', 'Sin análisis', null, 'tt-gris');
    }
    tooltip.appendChild(filas);
    return true;
  }

  function mostrarTooltip(id, puntero) {
    const it = itemPorId(id);
    if (!it || !armarTooltip(it)) { ocultarTooltip(); return; }
    tooltipId = id;
    tooltipAnclado = !puntero;
    tooltip.hidden = false;
    posicionarTooltip(puntero);
  }

  function posicionarTooltip(puntero) {
    const W = cont.clientWidth, H = cont.clientHeight;
    const tw = tooltip.offsetWidth, th = tooltip.offsetHeight;
    let left, top;
    if (puntero) {
      left = puntero.x + 14;
      top = puntero.y + 14;
      if (left + tw > W) left = puntero.x - 14 - tw;
      if (top + th > H) top = puntero.y - 14 - th;
    } else {
      const it = itemPorId(tooltipId);
      const c = caja(puntosDeItem(it).map((p) => aPantalla(p[0], p[1])));
      left = (c.x1 + c.x2) / 2 - tw / 2;
      top = c.y1 - th - 10;
      if (top < 4) top = c.y2 + 10;
    }
    tooltip.style.left = limitar(left, 4, Math.max(4, W - tw - 4)) + 'px';
    tooltip.style.top = limitar(top, 4, Math.max(4, H - th - 4)) + 'px';
  }

  function ocultarTooltip() {
    clearTimeout(tooltipTimer);
    tooltipId = null;
    tooltipAnclado = false;
    tooltip.hidden = true;
  }

  /** Vuelve a armar el tooltip abierto (p. ej. al llegar revisiones nuevas). */
  function refrescarTooltip() {
    if (!tooltipId) return;
    if (!itemPorId(tooltipId)) { ocultarTooltip(); return; }
    mostrarTooltip(tooltipId, tooltipAnclado ? null : ultimoPuntero);
  }

  // =========================================================================
  //  Panel de propiedades
  // =========================================================================
  const RUMBOS = ['N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO'];
  /** La piquera está en el lado +y local: con rotación r apunta a (180 + r) mod 360. */
  const rumboPiquera = (rot) => RUMBOS[Math.round(normalizarAngulo(180 + (rot || 0)) / 45) % 8];
  const dosDecimales = (n) => String(Math.round(n * 100) / 100);

  /** Errores de validación de un elemento: { campo: mensaje }. */
  function erroresDe(it) {
    const errores = {};
    if (esColmena(it)) {
      const codigo = String(it.codigo || '').trim();
      if (!codigo) errores.codigo = 'El código es obligatorio.';
      else {
        const clave = normalizar(codigo);
        const repetido = items().some((o) => o.id !== it.id && esColmena(o) && normalizar(o.codigo) === clave);
        if (repetido) errores.codigo = 'Ya hay otra colmena o núcleo con el código ' + codigo + '.';
      }
    }
    if (it.tipo === 'etiqueta' && !String(it.texto || '').trim()) errores.texto = 'El texto es obligatorio.';
    return errores;
  }

  function mostrarError(input, mensaje) {
    const p = $(input.id + 'Error');
    input.classList.toggle('invalido', !!mensaje);
    input.setAttribute('aria-invalid', mensaje ? 'true' : 'false');
    if (p) { p.textContent = mensaje || ''; p.hidden = !mensaje; }
  }

  function sincronizarPanel() {
    const it = estado.modo === 'editar' ? itemPorId(estado.seleccion) : null;
    if (!it) { panelProp.hidden = true; return; }
    panelProp.hidden = false;
    $('mpTitulo').textContent = TIPOS[it.tipo].nombre;
    panelProp.querySelectorAll('.mp-campo').forEach((c) => {
      c.hidden = c.getAttribute('data-tipos').split(' ').indexOf(it.tipo) === -1;
    });
    const activo = document.activeElement;
    const poner = (input, valor) => { if (input !== activo) input.value = valor; };
    if (esColmena(it)) {
      poner(campos.codigo, it.codigo || '');
      poner(campos.reina, it.reina_fecha || '');
      poner(campos.notas, it.notas || '');
      campos.piquera.value = rumboPiquera(it.rot);
    }
    if (it.tipo !== 'etiqueta') poner(campos.alias, it.alias || '');
    if (it.tipo === 'colmena' || it.tipo === 'nucleo' || it.tipo === 'pallet') {
      poner(campos.ancho, dosDecimales(it.w));
      poner(campos.largo, dosDecimales(it.h));
    }
    if (TIPOS[it.tipo].segmento) poner(campos.largoSeg, dosDecimales(Math.hypot(it.x2 - it.x1, it.y2 - it.y1)));
    if (it.rot != null) poner(campos.rot, String(it.rot));
    if (it.tipo === 'etiqueta') {
      poner(campos.texto, it.texto || '');
      poner(campos.tam, it.tam || 'M');
    }
    const errores = erroresDe(it);
    mostrarError(campos.codigo, errores.codigo);
    mostrarError(campos.texto, errores.texto);
  }

  /** Aplica `cambios` al elemento seleccionado. `paso`: true = confirma un paso de deshacer. */
  function editarSeleccion(cambios, paso) {
    const it = itemPorId(estado.seleccion);
    if (!it) return;
    reemplazarItem(Object.assign({}, it, cambios));
    if (paso) confirmarPaso();
    sincronizarPanel();
  }

  function numeroDe(input) {
    if (input.value.trim() === '' || input.validity.badInput) return null;
    const n = Number(input.value);
    return isFinite(n) ? n : null;
  }

  /** Cambios de un campo numérico, o null si el valor no es válido. */
  function cambiosNumericos(campo, n) {
    const it = itemPorId(estado.seleccion);
    if (!it || n === null) return null;
    if (campo === 'ancho') return { w: limitar(redondear(n), LADO_MIN, LARGO_MAX) };
    if (campo === 'largo') return { h: limitar(redondear(n), LADO_MIN, LARGO_MAX) };
    if (campo === 'rot') return { rot: normalizarAngulo(n) };
    if (campo === 'largoSeg') {
      // Mueve el extremo final manteniendo la dirección.
      const dx = it.x2 - it.x1, dy = it.y2 - it.y1;
      const actual = Math.hypot(dx, dy);
      const dir = actual > 1e-9 ? [dx / actual, dy / actual] : [1, 0];
      const largo = limitar(n, SEGMENTO_MIN, LARGO_MAX);
      return { x2: limitarCoord(redondear(it.x1 + dir[0] * largo)), y2: limitarCoord(redondear(it.y1 + dir[1] * largo)) };
    }
    return null;
  }

  // Texto: cada tecla actualiza el plano; el paso de deshacer se confirma al salir del campo.
  [['codigo', 'codigo'], ['texto', 'texto'], ['alias', 'alias'], ['notas', 'notas']].forEach((par) => {
    const input = campos[par[0]];
    input.addEventListener('input', () => editarSeleccion({ [par[1]]: input.value }, false));
    input.addEventListener('change', () => editarSeleccion({ [par[1]]: input.value.trim() }, true));
  });
  campos.reina.addEventListener('change', () => editarSeleccion({ reina_fecha: campos.reina.value || '' }, true));
  campos.tam.addEventListener('change', () => editarSeleccion({ tam: campos.tam.value }, true));
  [['ancho', campos.ancho], ['largo', campos.largo], ['rot', campos.rot], ['largoSeg', campos.largoSeg]].forEach((par) => {
    const input = par[1];
    input.addEventListener('input', () => {
      const cambios = cambiosNumericos(par[0], numeroDe(input));
      if (cambios) editarSeleccion(cambios, false);
    });
    input.addEventListener('change', () => {
      const cambios = cambiosNumericos(par[0], numeroDe(input));
      if (cambios) editarSeleccion(cambios, true);
      // Valor inválido o fuera de rango: se vuelve a mostrar el valor real.
      if (document.activeElement === input) input.blur();
      sincronizarPanel();
    });
  });

  $('mpCerrar').addEventListener('click', deseleccionar);
  $('mpDuplicar').addEventListener('click', () => { if (estado.seleccion) duplicar(estado.seleccion); });
  $('mpEliminar').addEventListener('click', () => { if (estado.seleccion) borrar(estado.seleccion); });

  // =========================================================================
  //  Modo Ver / Editar y menú «+»
  // =========================================================================
  function ponerModo(modo) {
    if (modo === 'editar' && estado.edicionBloqueada) return;
    estado.modo = modo;
    const editando = modo === 'editar';
    btnVer.setAttribute('aria-pressed', editando ? 'false' : 'true');
    btnEditar.setAttribute('aria-pressed', editando ? 'true' : 'false');
    historial.hidden = !editando;
    agregarCaja.hidden = !editando;
    svg.classList.toggle('editando', editando);
    if (!editando) {
      cerrarMenu();
      estado.seleccion = null;
    }
    nodos.forEach((n) => { n.it = null; }); // tabindex / aria-label según el modo
    sincronizarPanel();
    actualizarEstadoVacio();
    pedirRender();
  }

  function actualizarDisponibilidadEdicion() {
    btnEditar.disabled = !!estado.edicionBloqueada;
    btnEditar.title = estado.edicionBloqueada ? 'No disponible hasta que el mapa cargue desde el servidor' : '';
    if (estado.edicionBloqueada && estado.modo === 'editar') ponerModo('ver');
  }

  btnVer.addEventListener('click', () => ponerModo('ver'));
  btnEditar.addEventListener('click', () => ponerModo('editar'));
  btnDeshacer.addEventListener('click', deshacer);
  btnRehacer.addEventListener('click', rehacer);

  function abrirMenu() {
    menu.hidden = false;
    btnAgregar.setAttribute('aria-expanded', 'true');
    ocultarTooltip();
  }
  function cerrarMenu() {
    if (menu.hidden) return;
    menu.hidden = true;
    btnAgregar.setAttribute('aria-expanded', 'false');
  }
  btnAgregar.addEventListener('click', () => (menu.hidden ? abrirMenu() : cerrarMenu()));
  menu.addEventListener('click', (e) => {
    const b = e.target.closest('[data-tipo]');
    if (!b) return;
    cerrarMenu();
    crear(b.getAttribute('data-tipo'));
  });
  document.addEventListener('pointerdown', (e) => {
    if (!menu.hidden && !menu.contains(e.target) && !btnAgregar.contains(e.target)) cerrarMenu();
  }, true);

  // =========================================================================
  //  Estados del lienzo (cargando, vacío, error)
  // =========================================================================
  function mostrarEstado(titulo, texto, opciones) {
    estadoEl.textContent = '';
    if (!titulo && !texto && !(opciones && opciones.spinner)) { estadoEl.hidden = true; return; }
    const caja = document.createElement('div');
    if (opciones && opciones.spinner) caja.appendChild(nodoTexto('div', 'spinner'));
    if (titulo) caja.appendChild(nodoTexto('h3', null, titulo));
    if (texto) caja.appendChild(nodoTexto('p', null, texto));
    if (opciones && opciones.reintentar) {
      const b = nodoTexto('button', 'btn ghost', 'Reintentar');
      b.type = 'button';
      b.addEventListener('click', cargarMapa);
      caja.appendChild(b);
    }
    estadoEl.appendChild(caja);
    estadoEl.hidden = false;
  }

  function actualizarEstadoVacio() {
    if (!estado.cargado || estado.edicionBloqueada) return;
    if (estado.modo === 'ver' && estado.mapa.items.length === 0) {
      mostrarEstado(null, 'El mapa todavía está vacío. Pasá a Editar y usá + para agregar colmenas, núcleos y límites.');
    } else {
      mostrarEstado(null, null);
    }
  }

  // =========================================================================
  //  Datos: carga del mapa
  // =========================================================================
  function mapaVacio() {
    return { esquema: 1, unidad: 'm', items: [] };
  }

  function urlMapa() {
    const u = B.url || '';
    return u + (u.indexOf('?') === -1 ? '?' : '&') + 'recurso=mapa';
  }

  /** Lienzo vacío en modo Ver, sin posibilidad de editar (sin servidor utilizable). */
  function bloquearEdicion(motivo, cargado) {
    estado.mapa = mapaVacio();
    estado.cargado = cargado;
    estado.edicionBloqueada = motivo;
    estado.seleccion = null;
    reiniciarHistorial();
    actualizarDisponibilidadEdicion();
    pedirRender();
  }

  function cargarMapa() {
    if (estado.cargando) return;
    if (!B.configurado) {
      bloquearEdicion('sin-configuracion', true);
      mostrarEstado('Sin conexión a la hoja de datos', 'Conectá tu hoja de Google para ver y guardar el mapa (ver README).');
      return;
    }
    estado.cargando = true;
    mostrarEstado(null, 'Cargando mapa…', { spinner: true });
    fetch(urlMapa(), { method: 'GET' })
      .then((r) => r.json())
      .then((res) => {
        estado.cargando = false;
        if (!res || !res.ok) {
          errorDeCarga((res && res.error) || 'Error desconocido');
          return;
        }
        if (typeof res.version !== 'number') {
          // El Codigo.gs viejo ignora ?recurso=mapa y devuelve las revisiones.
          bloquearEdicion('script-viejo', true);
          mostrarEstado(null, 'Falta actualizar el script de Google para usar el mapa (ver README → Actualizar el script).');
          return;
        }
        aplicarMapaServidor(res);
      })
      .catch((err) => {
        estado.cargando = false;
        errorDeCarga(err && err.message ? err.message : String(err));
      });
  }

  function errorDeCarga(detalle) {
    if (!estado.cargado) bloquearEdicion('error', false);
    mostrarEstado('No se pudo cargar el mapa', detalle, { reintentar: true });
  }

  function aplicarMapaServidor(res) {
    const data = res.data && Array.isArray(res.data.items) ? res.data : mapaVacio();
    ponerItems(data.items);
    estado.versionBase = res.version;
    estado.cargado = true;
    estado.edicionBloqueada = null;
    if (estado.seleccion && !itemPorId(estado.seleccion)) estado.seleccion = null;
    reiniciarHistorial();
    actualizarDisponibilidadEdicion();
    sincronizarPanel();
    actualizarDatalist();
    actualizarEstadoVacio();
    ajustar();
  }

  /** Sugerencias de #numero_colmena con los códigos de colmenas y núcleos. */
  function actualizarDatalist() {
    const dl = document.getElementById('codigosMapa');
    if (!dl) return;
    const codigos = estado.mapa.items.filter(esColmena).map((it) => it.codigo)
      .sort((a, b) => a.localeCompare(b, 'es', { numeric: true }));
    dl.textContent = '';
    codigos.forEach((c) => {
      const o = document.createElement('option');
      o.value = c;
      dl.appendChild(o);
    });
  }

  // =========================================================================
  //  Interacción (Pointer Events: mouse, lápiz y touch)
  // =========================================================================
  const punteros = new Map(); // pointerId -> {x, y}
  let gesto = null;

  function posicion(e) {
    const r = svg.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }
  function idBajo(e) {
    const g = e.target && e.target.closest ? e.target.closest('[data-id]') : null;
    return g ? g.getAttribute('data-id') : null;
  }

  function iniciarPinch() {
    const [a, b] = Array.from(punteros.values());
    const v = estado.vista;
    gesto = {
      tipo: 'pinch',
      d0: Math.hypot(b.x - a.x, b.y - a.y) || 1,
      centro0: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 },
      s0: v.s, tx0: v.tx, ty0: v.ty
    };
  }

  svg.addEventListener('pointerdown', (e) => {
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    svg.setPointerCapture(e.pointerId);
    const p = posicion(e);
    punteros.set(e.pointerId, p);
    if (punteros.size === 2) {
      terminarEdicion(); // un segundo dedo convierte el arrastre en pellizco
      iniciarPinch();
      ocultarTooltip();
      return;
    }
    if (punteros.size > 2) return;
    cerrarMenu();
    if (estado.modo === 'editar') {
      const asa = e.target.closest ? e.target.closest('[data-asa]') : null;
      const seleccionado = itemPorId(estado.seleccion);
      if (asa && seleccionado) {
        const cual = asa.getAttribute('data-asa');
        gesto = {
          tipo: 'asa', asa: cual, original: seleccionado, inicio: p, movio: false,
          inicioMundo: aMundo(p.x, p.y), ancla: anclaDeAsa(seleccionado, cual)
        };
        return;
      }
      const id = idBajo(e);
      if (id) {
        if (id !== estado.seleccion) seleccionar(id);
        gesto = { tipo: 'mover', original: itemPorId(id), inicio: p, inicioMundo: aMundo(p.x, p.y), movio: false };
        return;
      }
    }
    const v = estado.vista;
    gesto = {
      tipo: 'pan', inicio: p, tx0: v.tx, ty0: v.ty, movio: false,
      objetivo: idBajo(e), pointerType: e.pointerType
    };
  });

  /** Cierra un arrastre de edición: un solo paso de deshacer por gesto. */
  function terminarEdicion() {
    if (!gesto || (gesto.tipo !== 'mover' && gesto.tipo !== 'asa')) return;
    const fue = gesto;
    gesto = null;
    svg.classList.remove('arrastrando');
    if (fue.movio) {
      confirmarPaso();
      sincronizarPanel();
    }
  }

  svg.addEventListener('pointermove', (e) => {
    const p = posicion(e);
    if (punteros.has(e.pointerId)) punteros.set(e.pointerId, p);

    if (gesto && gesto.tipo === 'pinch' && punteros.size >= 2) {
      const [a, b] = Array.from(punteros.values());
      const d = Math.hypot(b.x - a.x, b.y - a.y) || 1;
      const centro = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
      const v = estado.vista;
      const s = limitar(gesto.s0 * d / gesto.d0, ZOOM_MIN, ZOOM_MAX);
      // El punto del mundo que estaba bajo el centro inicial sigue al centro actual.
      const wx = (gesto.centro0.x - gesto.tx0) / gesto.s0;
      const wy = (gesto.centro0.y - gesto.ty0) / gesto.s0;
      v.s = s;
      v.tx = centro.x - wx * s;
      v.ty = centro.y - wy * s;
      pedirRender();
      return;
    }

    if (gesto && (gesto.tipo === 'mover' || gesto.tipo === 'asa') && punteros.has(e.pointerId)) {
      if (!gesto.movio && Math.hypot(p.x - gesto.inicio.x, p.y - gesto.inicio.y) < 3) return; // < 3 px = clic
      if (!gesto.movio) {
        gesto.movio = true;
        svg.classList.add('arrastrando');
        ocultarTooltip();
      }
      const w = aMundo(p.x, p.y);
      const dx = w[0] - gesto.inicioMundo[0], dy = w[1] - gesto.inicioMundo[1];
      if (gesto.tipo === 'mover') {
        reemplazarItem(moverItem(gesto.original, dx, dy, e.altKey));
      } else {
        // Esquinas y extremos se mueven en relación con donde se agarró el asa
        // (que puede estar separada del punto real); la rotación usa el puntero.
        const objetivo = gesto.ancla ? [gesto.ancla[0] + dx, gesto.ancla[1] + dy] : w;
        reemplazarItem(aplicarAsa(gesto.original, gesto.asa, objetivo, e.altKey));
      }
      return;
    }

    if (gesto && gesto.tipo === 'pan' && punteros.has(e.pointerId)) {
      const dx = p.x - gesto.inicio.x, dy = p.y - gesto.inicio.y;
      if (!gesto.movio && Math.hypot(dx, dy) < 3) return; // < 3 px = clic
      if (!gesto.movio) {
        gesto.movio = true;
        svg.classList.add('arrastrando');
        ocultarTooltip();
      }
      estado.vista.tx = gesto.tx0 + dx;
      estado.vista.ty = gesto.ty0 + dy;
      pedirRender();
      return;
    }

    // Sin gesto: hover con mouse o lápiz -> tooltip con 80 ms de retardo.
    if (e.pointerType === 'touch') return;
    ultimoPuntero = p;
    const id = idBajo(e);
    if (id && id === tooltipId && !tooltipAnclado) { posicionarTooltip(p); return; }
    clearTimeout(tooltipTimer);
    if (!id) { if (!tooltipAnclado) ocultarTooltip(); return; }
    tooltipTimer = setTimeout(() => mostrarTooltip(id, ultimoPuntero), 80);
  });

  function terminarPuntero(e) {
    if (!punteros.has(e.pointerId)) return;
    punteros.delete(e.pointerId);
    if (gesto && gesto.tipo === 'pinch') {
      // Al levantar un dedo, el otro sigue desplazando sin saltos.
      if (punteros.size === 1) {
        const v = estado.vista;
        const restante = Array.from(punteros.values())[0];
        gesto = { tipo: 'pan', inicio: restante, tx0: v.tx, ty0: v.ty, movio: true, objetivo: null, pointerType: 'touch' };
      } else if (!punteros.size) {
        gesto = null;
      }
      return;
    }
    if (gesto && (gesto.tipo === 'mover' || gesto.tipo === 'asa')) {
      const toque = !gesto.movio && e.type === 'pointerup';
      terminarEdicion();
      if (toque) asegurarVisible();
      return;
    }
    if (gesto && gesto.tipo === 'pan' && !punteros.size) {
      const fue = gesto;
      gesto = null;
      svg.classList.remove('arrastrando');
      if (!fue.movio && e.type === 'pointerup') {
        if (estado.modo === 'editar') {
          deseleccionar(); // clic o toque en vacío
        } else if (fue.pointerType !== 'mouse') {
          // Toque: muestra el tooltip anclado sobre el elemento, o lo cierra.
          if (fue.objetivo && fue.objetivo !== tooltipId) mostrarTooltip(fue.objetivo, null);
          else ocultarTooltip();
        }
      }
    }
  }
  svg.addEventListener('pointerup', terminarPuntero);
  svg.addEventListener('pointercancel', terminarPuntero);
  // Táctil: tocar en cualquier lugar fuera del plano cierra el tooltip anclado.
  document.addEventListener('pointerdown', (e) => {
    if (tooltipAnclado && !svg.contains(e.target)) ocultarTooltip();
  }, true);
  svg.addEventListener('pointerleave', (e) => {
    if (e.pointerType !== 'touch' && !tooltipAnclado) ocultarTooltip();
  });

  svg.addEventListener('wheel', (e) => {
    e.preventDefault();
    const unidad = e.deltaMode === 1 ? 16 : (e.deltaMode === 2 ? 400 : 1);
    const p = posicion(e);
    zoomEn(p.x, p.y, Math.exp(-e.deltaY * unidad * 0.0015));
    if (tooltipId) {
      if (tooltipAnclado) posicionarTooltip(null);
      else ocultarTooltip();
    }
  }, { passive: false });

  $('mapaZoomMas').addEventListener('click', () => zoomCentro(1.25));
  $('mapaZoomMenos').addEventListener('click', () => zoomCentro(1 / 1.25));
  $('mapaAjustar').addEventListener('click', ajustar);

  function esCampoDeTexto(n) {
    return n && (n.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(n.tagName));
  }

  const FLECHAS = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };

  /** Atajos del modo Editar. Devuelve true si la tecla ya se atendió. */
  function teclaEdicion(e, enCampo) {
    const mod = e.ctrlKey || e.metaKey;
    const tecla = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    if (mod && !enCampo && tecla === 'z') { e.preventDefault(); if (e.shiftKey) rehacer(); else deshacer(); return true; }
    if (mod && !enCampo && tecla === 'y') { e.preventDefault(); rehacer(); return true; }
    if (mod && !enCampo && tecla === 'd') { e.preventDefault(); if (estado.seleccion) duplicar(estado.seleccion); return true; }
    if (enCampo) {
      if (e.key === 'Escape') e.target.blur();
      return true;
    }
    if (e.key === 'Escape') {
      if (!menu.hidden) { cerrarMenu(); btnAgregar.focus(); } else deseleccionar();
      return true;
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && estado.seleccion) {
      e.preventDefault();
      borrar(estado.seleccion);
      return true;
    }
    if (FLECHAS[e.key] && estado.seleccion && !mod) {
      e.preventDefault();
      const paso = e.shiftKey ? 0.5 : 0.05; // 50 cm / 5 cm
      empujar(FLECHAS[e.key][0] * paso, FLECHAS[e.key][1] * paso);
      return true;
    }
    if (e.key === 'Enter') {
      const g = e.target.closest ? e.target.closest('[data-id]') : null;
      if (g) {
        e.preventDefault();
        seleccionar(g.getAttribute('data-id'));
        asegurarVisible();
        return true;
      }
    }
    return false;
  }

  document.addEventListener('keydown', (e) => {
    if (B.tab !== 'mapa') return;
    const enCampo = esCampoDeTexto(e.target);
    if (estado.modo === 'editar' && teclaEdicion(e, enCampo)) return;
    if (enCampo || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === '+' || e.key === '=') { zoomCentro(1.25); e.preventDefault(); }
    else if (e.key === '-' || e.key === '_') { zoomCentro(1 / 1.25); e.preventDefault(); }
    else if (e.key === '0') { ajustar(); e.preventDefault(); }
    else if (e.key === 'Escape') { ocultarTooltip(); }
  });

  // =========================================================================
  //  Pestaña: medidas, carga perezosa y tamaño
  // =========================================================================
  function medir() {
    const header = document.querySelector('.top');
    const tabs = document.querySelector('.tabs');
    const offset = (header ? header.offsetHeight : 0) + (tabs ? tabs.offsetHeight : 0) + 40;
    cont.style.setProperty('--mapa-offset', offset + 'px');
  }

  function alMostrar() {
    medir();
    if (!estado.cargado) cargarMapa();
    requestAnimationFrame(() => {
      if (estado.ajustarPendiente && estado.cargado) ajustar();
      pedirRender();
    });
  }

  let tamAnterior = { w: 0, h: 0 };
  new ResizeObserver(() => {
    const t = tamLienzo();
    if (!t.w || !t.h) return;
    // Mantener el centro de la vista al cambiar el tamaño del lienzo.
    if (tamAnterior.w && tamAnterior.h) {
      estado.vista.tx += (t.w - tamAnterior.w) / 2;
      estado.vista.ty += (t.h - tamAnterior.h) / 2;
    }
    tamAnterior = t;
    if (estado.ajustarPendiente && estado.cargado) ajustar();
    pedirRender();
  }).observe(cont);

  window.addEventListener('resize', () => { if (!panel.hidden) medir(); });

  document.addEventListener('bitacora:tab', (e) => {
    if (e.detail === 'mapa') alMostrar();
    else ocultarTooltip();
    // El formulario también usa los códigos del mapa (datalist de #numero_colmena).
    if (e.detail === 'nueva' && !estado.cargado) cargarMapa();
  });

  document.addEventListener('bitacora:revisiones', (e) => indexarRevisiones(e.detail));

  // ---- Inicio --------------------------------------------------------------
  actualizarDisponibilidadEdicion();
  if (B.revisiones) indexarRevisiones(B.revisiones);
  if (B.tab === 'mapa') alMostrar();
  else if (B.tab === 'nueva') cargarMapa();
})();
