/** Config de Interfaz 4 (contexto meteorológico de visitas). */
window.INTERFAZ4_CFG = {
  REPO: 'eduabejas/apiario-portal',
  RAMA: 'main',
  // Estado que publica el motor (GitHub Actions) en cada cambio. Se lee de
  // raw.githubusercontent.com (CORS abierto, caché de 5 min) y, si falla, de
  // la copia que despliega Pages.
  DATOS_RAW: 'https://raw.githubusercontent.com/eduabejas/apiario-portal/main/interfaz4/publico/',
  DATOS_PAGES: 'interfaz4/publico/',
  WORKFLOW_MOTOR: 'interfaz4.yml',
  HITOS: [24, 12],
  APIARIOS: {
    produccion_miel: { nombre: 'Apiario de producción melífera', localidad: 'Berisso, Buenos Aires' }
  }
};
