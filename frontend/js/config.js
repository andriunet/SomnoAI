/* ════════════════════════════════════════════════════════════════════
   Configuración del tablero MAIA / SomnoAI
   ────────────────────────────────────────────────────────────────────
   apiBase:
     - null  → modo DEMO: el tablero funciona solo, con un backend
               simulado en el navegador (js/mock.js). Los análisis se
               guardan en localStorage.
     - URL   → modo REAL: apuntar a la API de FastAPI, p. ej.
               "http://localhost:8000/api/v1"
               El contrato que la API debe cumplir está en
               docs/API_CONTRACT.md.
   ════════════════════════════════════════════════════════════════════ */
window.MAIA_CONFIG = {
  // Se deriva del host desde el que se abrió el tablero: sirve igual en
  // localhost que en la EC2, sin escribir ninguna IP en el repo.
  apiBase: "http://" + location.hostname + ":8000/api/v1",   // ← null = modo demo (mock)

  // Tiempo máximo de espera para POST /predict (el análisis real
  // de un EDF puede tardar minutos: carga + estadificación + espectros).
  analyzeTimeoutMs: 10 * 60 * 1000,

  // Tiempo máximo para el resto de peticiones.
  requestTimeoutMs: 30 * 1000,

  // Límite de carga que muestra/valida el front (la API debe validar igual).
  maxUploadMB: 600,

  // Umbral de priorización |BAI| en años (la API lo confirma por registro).
  thresholdYears: 10
};
