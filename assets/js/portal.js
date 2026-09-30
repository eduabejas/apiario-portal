/**
 * Portal de selección (index.html): componente Alpine + marcador de
 * acceso directo (?u=rocio&i=3 → salta a interfaz3.html?u=rocio), tal
 * como hacía /exec?u=...&i=... en la versión Apps Script.
 */
(function () {
  var params = new URLSearchParams(location.search);
  var u = (params.get('u') || '').toLowerCase();
  var i = params.get('i') || '';
  var usuarios = window.APIARIO_USUARIOS || {};
  var interfaces = window.APIARIO_INTERFACES || {};
  if (usuarios[u] && interfaces[i]) {
    location.replace(interfaces[i].pagina + '?u=' + encodeURIComponent(u));
  }
})();

document.addEventListener('alpine:init', function () {
  Alpine.data('portal', function () {
    return {
      usuario: '',
      interfaz: '',
      usuarios: window.APIARIO_USUARIOS || {},
      interfaces: window.APIARIO_INTERFACES || {},
      get puedeEntrar() {
        return !!this.usuario && !!this.interfaz;
      },
      entrar: function () {
        if (!this.puedeEntrar) return;
        var pagina = this.interfaces[this.interfaz].pagina;
        window.location.href = pagina + '?u=' + encodeURIComponent(this.usuario);
      }
    };
  });
});
