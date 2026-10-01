/** Rellena el chip de usuario (#user-chip) según ?u= en la URL. */
function apiarioRenderChip() {
  var chip = document.getElementById('user-chip');
  if (!chip) return;
  var usuario = window.apiarioUsuarioActual ? window.apiarioUsuarioActual() : null;
  chip.textContent = '👤 ' + (usuario ? usuario.nombre : 'Invitado');
}
window.apiarioRenderChip = apiarioRenderChip;
document.addEventListener('DOMContentLoaded', apiarioRenderChip);
