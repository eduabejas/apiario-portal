/**
 * Interfaz 4 (contexto meteorológico de visitas): componente Alpine.
 *
 * - Ida: el formulario arma un issue de GitHub precargado; al crearlo, el
 *   workflow interfaz4-registro agenda la visita y responde en el issue.
 * - Vuelta: lista las visitas y el estado de sus informes leyendo
 *   interfaz4/publico/estado.json (lo publica el motor), y muestra cada
 *   informe enviado tal como llegó por correo.
 */
document.addEventListener('alpine:init', function () {
  var cfg = window.INTERFAZ4_CFG;
  var core = window.Interfaz4Core;

  function obtener(rutaRelativa, tipo) {
    var urls = [cfg.DATOS_RAW + rutaRelativa + '?t=' + Date.now(), cfg.DATOS_PAGES + rutaRelativa];
    var intentar = function (i) {
      return fetch(urls[i], { cache: 'no-store' }).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return tipo === 'json' ? r.json() : r.text();
      }).catch(function (e) {
        if (i + 1 < urls.length) return intentar(i + 1);
        throw e;
      });
    };
    return intentar(0);
  }

  Alpine.data('interfaz4', function () {
    return {
      ahora: new Date(),
      form: { apiario: 'produccion_miel', fecha: '', desde: '09:00', hasta: '13:00', responsable: '', notas: '' },
      intentoEnvio: false,
      abiertoGitHub: false,
      estado: null,
      cargando: true,
      errorCarga: '',
      cargadoEn: null,
      pestania: 'proximas',
      motor: null,
      modal: { abierto: false, titulo: '', html: '', cargando: false, error: '' },

      iniciar: function () {
        var usuario = window.apiarioUsuarioActual ? window.apiarioUsuarioActual() : null;
        if (usuario) this.form.responsable = usuario.nombre;
        this.form.fecha = core.fechaAR(this.ahora, 1);
        this.cargar();
        this.cargarMotor();
        var self = this;
        setInterval(function () { self.ahora = new Date(); }, 30000);
      },

      get apiarios() {
        var desdeEstado = this.estado && this.estado.apiarios;
        return desdeEstado && Object.keys(desdeEstado).length ? desdeEstado : cfg.APIARIOS;
      },
      get hitos() { return (this.estado && this.estado.hitos_horas) || cfg.HITOS; },
      get errores() { return core.validarVisita(this.form, this.ahora); },
      get agenda() {
        if (!core.fechaValida(this.form.fecha) || !core.horaValida(this.form.desde)) return null;
        var a = core.agendaInformes(this.form.fecha, this.form.desde, this.hitos, this.ahora);
        return {
          nota: a.nota,
          items: a.items.map(function (i) {
            var texto = i.accion === 'inmediato' ? 'apenas se registre (su momento ya pasó)'
              : i.accion === 'omitido' ? 'no se envía (su momento ya pasó)' : core.fmtMomento(i.momento);
            return { horas: i.horas, texto: texto };
          })
        };
      },
      get resumenVisita() {
        if (!core.fechaValida(this.form.fecha)) return '';
        return core.fmtDiaFecha(core.instante(this.form.fecha, '12:00')) + ' · ' + this.form.desde + '–' + this.form.hasta + ' (hora Argentina)';
      },
      get urlRegistro() {
        var ap = this.apiarios[this.form.apiario];
        return core.urlNuevaVisita(cfg.REPO, this.form, ap ? ap.nombre : '');
      },

      registrar: function () {
        this.intentoEnvio = true;
        if (this.errores.length) return;
        window.open(this.urlRegistro, '_blank', 'noopener');
        this.abiertoGitHub = true;
      },

      cargar: function () {
        var self = this;
        self.cargando = true;
        self.errorCarga = '';
        return obtener('estado.json', 'json').then(function (datos) {
          self.estado = datos;
          self.cargadoEn = new Date();
        }).catch(function (e) {
          self.errorCarga = 'No se pudo leer el estado del motor (' + e.message + ').';
        }).then(function () { self.cargando = false; });
      },

      cargarMotor: function () {
        var self = this;
        var url = 'https://api.github.com/repos/' + cfg.REPO + '/actions/workflows/' + cfg.WORKFLOW_MOTOR + '/runs?per_page=1&branch=' + cfg.RAMA;
        fetch(url, { headers: { Accept: 'application/vnd.github+json' } })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (d) {
            var run = d && d.workflow_runs && d.workflow_runs[0];
            if (run) self.motor = { fecha: new Date(run.updated_at), conclusion: run.conclusion, estado: run.status, url: run.html_url };
          })
          .catch(function () { /* el panel funciona igual sin este dato */ });
      },

      get listas() { return core.separarVisitas(this.estado ? this.estado.visitas : [], this.ahora); },
      get visitasVisibles() { return this.pestania === 'proximas' ? this.listas.proximas : this.listas.anteriores; },

      nombreApiario: function (id) { var a = this.apiarios[id]; return a ? a.nombre : id; },
      fechaVisita: function (v) { return core.fmtDiaFecha(new Date(v.inicio)) + ' · ' + v.desde + '–' + v.hasta; },
      textoHito: function (h) { return core.textoHito(h); },
      erroresHito: function (h) {
        return h.errores ? Object.keys(h.errores).map(function (c) { return c + ': ' + h.errores[c]; }) : [];
      },
      claseHito: function (h) {
        if (h.estado === 'enviado') return 'border-ok/40 bg-ok/10 text-ok';
        if (h.estado === 'error' || h.estado === 'parcial') return 'border-critico/40 bg-critico/10 text-critico';
        return 'border-borde bg-white/70 text-gris';
      },
      relativo: function (d) { return core.tiempoRelativo(d, this.ahora); },
      momentoCorto: function (d) { return core.fmtCorto(d); },

      cancelar: function (v) {
        var texto = '¿Cancelar la visita del ' + this.fechaVisita(v) + '?\nSe abre GitHub con el pedido precargado: confirmalo con "Create".';
        if (window.confirm(texto)) window.open(core.urlCancelar(cfg.REPO, v.id), '_blank', 'noopener');
      },

      verInforme: function (v, h) {
        var self = this;
        self.modal = { abierto: true, titulo: 'Informe ' + h.horas + ' h · ' + self.fechaVisita(v), html: '', cargando: true, error: '' };
        obtener(h.informe, 'text').then(function (html) {
          self.modal.html = '<base target="_blank">' + html;
        }).catch(function (e) {
          self.modal.error = 'No se pudo abrir el informe (' + e.message + ').';
        }).then(function () { self.modal.cargando = false; });
      },
      cerrarModal: function () { this.modal.abierto = false; this.modal.html = ''; }
    };
  });
});
