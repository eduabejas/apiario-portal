/* ===========================================================================
   Bitácora de colmenas — lógica de la aplicación
   Backend: Google Sheets vía Apps Script.
   Lectura pública (GET) + escritura protegida por código (POST, validado en el
   servidor).
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
    reservas_miel:   { "Alta": "good", "Media": "mid", "Baja": "bad" },
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
  function hoyISO() {
    var h = new Date();
    return h.getFullYear() + "-" + String(h.getMonth() + 1).padStart(2, "0") + "-" + String(h.getDate()).padStart(2, "0");
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

  /* ---------- Tabs ---------- */
  var tabLista = $("#tabListaBtn"), tabForm = $("#tabFormBtn");
  var panelLista = $("#panelLista"), panelForm = $("#panelForm");
  function mostrarTab(cual) {
    var esLista = cual === "lista";
    tabLista.setAttribute("aria-selected", esLista ? "true" : "false");
    tabForm.setAttribute("aria-selected", esLista ? "false" : "true");
    panelLista.hidden = !esLista;
    panelForm.hidden = esLista;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  tabLista.addEventListener("click", function () { mostrarTab("lista"); });
  tabForm.addEventListener("click", function () { mostrarTab("form"); });

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

  /* ---------- Fecha por defecto = hoy ---------- */
  $("#fecha").value = hoyISO();

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
        "<p>Cuando registres una revisión, aparecerá acá.</p></div>");
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
      })
      .catch(function (err) {
        estado('<div class="state"><h3>No se pudieron cargar los registros</h3><p>' +
          esc(err && err.message ? err.message : String(err)) + "</p></div>");
      });
  }

  /* ---------- Acaricida => marcar "Trató varroa" (no se desmarca al borrar) ---------- */
  $("#acaricida").addEventListener("input", function () {
    if (!this.value.trim()) return;
    var chip = document.querySelector('#accionesChips input[value="Trató varroa"]');
    if (chip) chip.checked = true;
  });

  /* ---------- Guardar revisión ---------- */
  function mensaje(tipo, texto) {
    $("#formMsg").innerHTML = '<div class="msg ' + tipo + '">' + esc(texto) + "</div>";
  }

  $("#revForm").addEventListener("submit", function (ev) {
    ev.preventDefault();
    $("#formMsg").innerHTML = "";

    var numero = $("#numero_colmena").value.trim();
    var fecha = $("#fecha").value;
    var codigo = $("#codigo").value;

    var varroaInput = $("#varroa_pct");
    var varroaTexto = varroaInput.value.trim();
    var varroaN = Number(varroaTexto);

    if (!numero) { mensaje("err", "Indicá el número de colmena."); $("#numero_colmena").focus(); return; }
    if (!fecha) { mensaje("err", "Indicá la fecha de revisión."); $("#fecha").focus(); return; }
    if (varroaInput.validity.badInput || (varroaTexto !== "" && (!isFinite(varroaN) || varroaN < 0 || varroaN > 100))) {
      mensaje("err", "El análisis de varroa debe ser un número entre 0 y 100.");
      varroaInput.focus();
      return;
    }
    if (!codigo) { mensaje("err", "Ingresá el código de acceso para poder guardar."); $("#codigo").focus(); return; }
    if (!configurado) { mensaje("err", "El sitio aún no está conectado a la hoja de Google (ver README)."); return; }

    var acciones = [];
    document.querySelectorAll('#accionesChips input:checked').forEach(function (c) { acciones.push(c.value); });

    var datos = {
      fecha: fecha,
      numero_colmena: numero,
      apiario: $("#apiario").value.trim(),
      postura: $("#postura").value,
      estado_reina: $("#estado_reina").value,
      cria_operculada: $("#cria_operculada").value,
      reservas_miel: $("#reservas_miel").value,
      reservas_polen: $("#reservas_polen").value,
      reina_vista: $("#reina_vista").value,
      huevos: $("#huevos").value,
      poblacion: $("#poblacion").value,
      temperamento: $("#temperamento").value,
      sanidad: $("#sanidad").value,
      celdas_reales: $("#celdas_reales").value,
      acciones: acciones,
      observaciones: $("#observaciones").value.trim(),
      registrado_por: $("#registrado_por").value.trim(),
      varroa_pct: varroaTexto,
      acaricida: $("#acaricida").value.trim().slice(0, 60)
    };

    var btn = $("#submitBtn");
    btn.disabled = true; btn.textContent = "Guardando…";

    // POST como "simple request" (sin cabeceras extra) para evitar preflight CORS.
    fetch(URL, { method: "POST", body: JSON.stringify({ codigo: codigo, datos: datos }) })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        btn.disabled = false; btn.textContent = "Guardar revisión";
        if (!res || !res.ok) {
          var m = (res && res.error) || "";
          if (/inv[aá]lido/i.test(m)) mensaje("err", "Código de acceso inválido. Verificá e intentá de nuevo.");
          else mensaje("err", "No se pudo guardar: " + m);
          return;
        }
        mensaje("ok", "Revisión de la colmena " + numero + " guardada correctamente.");
        var form = $("#revForm");
        form.reset();
        $("#codigo").value = codigo;   // conservamos el código para cargas seguidas
        $("#fecha").value = hoyISO();
        cargar();
        setTimeout(function () { mostrarTab("lista"); }, 700);
      })
      .catch(function (err) {
        btn.disabled = false; btn.textContent = "Guardar revisión";
        mensaje("err", "No se pudo guardar: " + (err && err.message ? err.message : String(err)));
      });
  });

  /* ---------- Inicio ---------- */
  cargar();
})();
