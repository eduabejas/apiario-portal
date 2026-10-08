/* ===========================================================================
   Bitácora de colmenas — Registros y mapa (Interfaz 5)
   Backend: Google Sheets vía Apps Script. Lectura pública (GET); las
   revisiones se cargan desde el celular en la Interfaz 3 (interfaz3.html),
   que escribe en la misma hoja con el código de acceso.
   =========================================================================== */
(function () {
  "use strict";

  var cfg = window.APP_CONFIG || {};
  var URL = cfg.WEBAPP_URL || "";
  var configurado = URL && URL.indexOf("PEGA-AQUI") === -1;

  /* ---------- Semántica de colores por campo ---------- */
  var QUALITY = {
    postura:         { "Alta": "good", "Media": "mid", "Baja": "bad" },
    estado_reina:    { "Excelente": "good", "Regular": "mid", "Mala": "bad" },
    cria_operculada: { "Alta": "good", "Media": "mid", "Baja": "bad" },
    reservas_miel:   { "Alta": "good", "Media": "mid", "Baja": "bad", "Nula": "bad" },
    reservas_polen:  { "Alta": "good", "Media": "mid", "Baja": "bad" },
    poblacion:       { "Fuerte": "good", "Media": "mid", "Débil": "bad" },
    reina_vista:     { "Sí": "good", "No": "bad", "No buscada": "mid" },
    huevos:          { "Sí": "good", "No": "bad" },
    temperamento:    { "Manso": "good", "Normal": "mid", "Agresivo": "bad" },
    sanidad:         { "Sin signos": "good", "Leve": "mid", "Alta": "bad" },
    celdas_reales:   { "No": "good", "Enjambrazón": "bad", "Supersedura": "mid", "Emergencia": "bad" }
  };
  var METRICS = [
    ["postura", "Postura"], ["estado_reina", "Reina"], ["cria_operculada", "Cría operc."],
    ["reservas_miel", "Miel"], ["reservas_polen", "Polen"], ["poblacion", "Población"],
    ["reina_vista", "Reina vista"], ["huevos", "Huevos"], ["temperamento", "Temperam."],
    ["sanidad", "Sanidad"], ["celdas_reales", "Celdas real."]
  ];
  // Varroa (%): verde < 2, ámbar 2–<3, rojo ≥ 3 (mismo umbral de alerta que el mapa).
  var VARROA_ATENCION = 2.0;
  var VARROA_ALERTA = 3.0;

  /* ---------- Utilidades ---------- */
  function $(sel) { return document.querySelector(sel); }
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  var MESES = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
  function fechaBonita(iso) {
    if (!iso) return "";
    var p = String(iso).split("-");
    if (p.length < 3) return esc(iso);
    return parseInt(p[2], 10) + " " + MESES[parseInt(p[1], 10) - 1] + " " + p[0];
  }

  /* ---------- Tema ---------- */
  var root = document.documentElement;
  try {
    var savedTheme = localStorage.getItem("tema");
    if (savedTheme) root.setAttribute("data-theme", savedTheme);
  } catch (e) {}
  $("#themeToggle").addEventListener("click", function () {
    var actual = root.getAttribute("data-theme");
    var esOscuro = actual
      ? actual === "dark"
      : window.matchMedia("(prefers-color-scheme: dark)").matches;
    var nuevo = esOscuro ? "light" : "dark";
    root.setAttribute("data-theme", nuevo);
    try { localStorage.setItem("tema", nuevo); } catch (e) {}
  });

  /* ---------- Contrato compartido con otros módulos (mapa.js) ---------- */
  // El código de acceso vive solo en memoria: nunca en localStorage ni en la URL.
  var BITACORA = window.BITACORA = window.BITACORA || {};
  BITACORA.url = URL;
  BITACORA.configurado = configurado;
  BITACORA.codigoSesion = "";
  BITACORA.esc = esc;
  BITACORA.fechaBonita = fechaBonita;
  BITACORA.revisiones = BITACORA.revisiones || null;

  function emitir(nombre, detalle) {
    document.dispatchEvent(new CustomEvent(nombre, { detail: detalle }));
  }

  /* ---------- Registrar revisión: Interfaz 3 (pensada para el celular) ---------- */
  var REGISTRAR = "../interfaz3.html" + location.search;
  $("#registrarLink").href = REGISTRAR;
  // Enlaces viejos a la pestaña «Nueva revisión» van directo a la Interfaz 3.
  if (location.hash === "#nueva") { location.replace(REGISTRAR); return; }

  /* ---------- Tabs ---------- */
  var TABS = [
    { btn: $("#tabListaBtn"), panel: $("#panelLista"), hash: "registros" },
    { btn: $("#tabMapaBtn"), panel: $("#panelMapa"), hash: "mapa" }
  ];
  function tabPorHash(hash) {
    for (var i = 0; i < TABS.length; i++) if (TABS[i].hash === hash) return TABS[i];
    return null;
  }
  function mostrarTab(hash, opciones) {
    var tab = tabPorHash(hash) || TABS[0];
    opciones = opciones || {};
    for (var i = 0; i < TABS.length; i++) {
      var activa = TABS[i] === tab;
      TABS[i].btn.setAttribute("aria-selected", activa ? "true" : "false");
      TABS[i].panel.hidden = !activa;
    }
    BITACORA.tab = tab.hash;
    if (!opciones.sinHash) history.replaceState(null, "", location.pathname + location.search + "#" + tab.hash);
    if (!opciones.sinScroll) window.scrollTo({ top: 0, behavior: "smooth" });
    emitir("bitacora:tab", tab.hash);
  }
  TABS.forEach(function (t) {
    t.btn.addEventListener("click", function () { mostrarTab(t.hash); });
  });
  window.addEventListener("hashchange", function () {
    if (location.hash === "#nueva") { location.replace(REGISTRAR); return; }
    var t = tabPorHash(location.hash.slice(1));
    if (t && t.hash !== BITACORA.tab) mostrarTab(t.hash, { sinHash: true });
  });
  // Pestaña inicial según el hash (#registros, #mapa). Los módulos que
  // cargan después (mapa.js) leen BITACORA.tab al iniciar.
  mostrarTab((tabPorHash(location.hash.slice(1)) || TABS[0]).hash, { sinHash: !location.hash, sinScroll: true });
  BITACORA.mostrarTab = mostrarTab;

  /* ---------- Aviso de configuración pendiente ---------- */
  if (!configurado) {
    var n = $("#configNotice");
    n.hidden = false;
    n.innerHTML =
      "<b>Falta conectar la hoja de Google.</b> Pegá la URL de la app web en " +
      "<code>assets/config.js</code> (campo <code>WEBAPP_URL</code>). " +
      "Mientras tanto, el sitio se ve pero no guarda ni lee datos. " +
      "Ver instrucciones en el README.";
  }

  /* ---------- Cargar y renderizar lista ---------- */
  var TODAS = [];
  function estado(html) { $("#listaContenedor").innerHTML = html; }

  function iconoColmena() {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="3"/><path d="M4 9h16M4 14h16"/></svg>';
  }

  function metricaHTML(campo, label, valor, calidad) {
    var q = calidad || (QUALITY[campo] && QUALITY[campo][valor]) || "none";
    var punto = q === "sin-punto" ? "" : '<span class="dot' + (q === "none" ? "" : " q-" + q) + '"></span>';
    return '<div class="metric"><span class="k">' + esc(label) + '</span>' +
      '<span class="v">' + punto + esc(valor) + "</span></div>";
  }

  /** Número de varroa_pct o null si la revisión no trae análisis. */
  function varroaNumero(v) {
    if (v === "" || v == null) return null;
    var n = Number(v);
    return isFinite(n) ? n : null;
  }
  function formatoPct(n) { return n.toFixed(1).replace(".", ",") + " %"; }

  function tarjetaHTML(r) {
    var metrics = "";
    for (var i = 0; i < METRICS.length; i++) {
      var campo = METRICS[i][0], label = METRICS[i][1], valor = r[campo];
      if (valor) metrics += metricaHTML(campo, label, valor);
    }
    var varroa = varroaNumero(r.varroa_pct);
    if (varroa !== null) {
      var qv = varroa >= VARROA_ALERTA ? "bad" : (varroa >= VARROA_ATENCION ? "mid" : "good");
      metrics += metricaHTML("varroa_pct", "Varroa", formatoPct(varroa), qv);
    }
    if (r.acaricida) metrics += metricaHTML("acaricida", "Acaricida", r.acaricida, "sin-punto");
    var acciones = "";
    if (r.acciones && r.acciones.length) {
      acciones = '<div class="rev-acciones">';
      for (var j = 0; j < r.acciones.length; j++) acciones += '<span class="tag">' + esc(r.acciones[j]) + "</span>";
      acciones += "</div>";
    }
    var obs = r.observaciones ? '<div class="rev-obs">' + esc(r.observaciones) + "</div>" : "";
    var quien = r.registrado_por ? " · " + esc(r.registrado_por) : "";
    var apiario = r.apiario ? "<small> · " + esc(r.apiario) + "</small>" : "";

    return '<article class="rev">' +
      '<div class="rev-head"><div class="rev-colmena">Colmena ' + esc(r.numero_colmena) + apiario + "</div>" +
      '<div class="rev-fecha">' + fechaBonita(r.fecha) + "</div></div>" +
      '<div class="rev-grid">' + metrics + "</div>" +
      obs + acciones +
      '<div class="rev-foot">Registrado ' + fechaBonita(String(r.creado_en || "").slice(0, 10)) + quien + "</div>" +
      "</article>";
  }

  function pintar(lista) {
    if (!lista.length) {
      estado('<div class="state">' + iconoColmena() + "<h3>Sin registros todavía</h3>" +
        "<p>Las revisiones que se cargan desde la Interfaz 3 aparecen acá.</p></div>");
      $("#contador").textContent = "";
      return;
    }
    var html = '<div class="cards">';
    for (var i = 0; i < lista.length; i++) html += tarjetaHTML(lista[i]);
    html += "</div>";
    estado(html);
    $("#contador").textContent = lista.length + (lista.length === 1 ? " registro" : " registros");
  }

  function filtrar() {
    var q = $("#buscar").value.trim().toLowerCase();
    if (!q) { pintar(TODAS); return; }
    pintar(TODAS.filter(function (r) {
      return String(r.numero_colmena).toLowerCase().indexOf(q) !== -1;
    }));
  }
  $("#buscar").addEventListener("input", filtrar);

  function cargar() {
    if (!configurado) {
      estado('<div class="state">' + iconoColmena() + "<h3>Sin conexión a la hoja de datos</h3>" +
        "<p>Conectá tu hoja de Google para ver y guardar registros (ver README).</p></div>");
      return;
    }
    estado('<div class="state"><div class="spinner"></div><p>Cargando registros…</p></div>');
    fetch(URL, { method: "GET" })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (!res || !res.ok) {
          estado('<div class="state"><h3>No se pudieron cargar los registros</h3><p>' +
            esc((res && res.error) || "Error desconocido") + "</p></div>");
          return;
        }
        TODAS = res.data || [];
        filtrar();
        BITACORA.revisiones = TODAS;
        emitir("bitacora:revisiones", TODAS);
      })
      .catch(function (err) {
        estado('<div class="state"><h3>No se pudieron cargar los registros</h3><p>' +
          esc(err && err.message ? err.message : String(err)) + "</p></div>");
      });
  }

  BITACORA.recargarRevisiones = cargar;

  /* ---------- Inicio ---------- */
  cargar();
})();
