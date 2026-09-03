/* ════════════════════════════════════════════════════════════════════
   MAIA · cliente de API
   ────────────────────────────────────────────────────────────────────
   Fachada única que usa el resto del tablero. Según js/config.js:
     - apiBase = null → delega en el backend simulado (js/mock.js)
     - apiBase = URL  → habla HTTP con la API real (docs/API_CONTRACT.md)
   Errores siempre normalizados a: { code, message }
   ════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  const CFG = window.MAIA_CONFIG;
  const useMock = () => !CFG.apiBase;

  const TOKEN_KEY = "maia_token";
  const USER_KEY = "maia_user";

  function authHeaders() {
    const t = sessionStorage.getItem(TOKEN_KEY);
    return t ? { Authorization: "Bearer " + t } : {};
  }

  async function http(path, { method = "GET", body, isForm = false, timeoutMs } = {}) {
    const ctrl = new AbortController();
    const to = setTimeout(() => ctrl.abort(), timeoutMs || CFG.requestTimeoutMs);
    let res;
    try {
      res = await fetch(CFG.apiBase + path, {
        method,
        headers: {
          ...(isForm ? {} : body ? { "Content-Type": "application/json" } : {}),
          ...authHeaders()
        },
        body: isForm ? body : body ? JSON.stringify(body) : undefined,
        signal: ctrl.signal
      });
    } catch (e) {
      throw e.name === "AbortError"
        ? { code: "timeout", message: "La petición tardó demasiado. Intente de nuevo." }
        : { code: "network", message: "No se pudo contactar la API. ¿Está corriendo el backend?" };
    } finally {
      clearTimeout(to);
    }
    if (res.status === 401) {
      MaiaAPI.clearSession();
      window.dispatchEvent(new CustomEvent("maia:unauthorized"));
      throw { code: "unauthorized", message: "La sesión expiró. Inicie sesión de nuevo." };
    }
    let data = null;
    try { data = await res.json(); } catch (e) { /* respuestas sin cuerpo */ }
    if (!res.ok) {
      const err = (data && data.error) || {};
      throw { code: err.code || "http_" + res.status, message: err.message || "Error del servidor (" + res.status + ")." };
    }
    return data;
  }

  window.MaiaAPI = {
    /* ── sesión ── */
    isLoggedIn: () => !!sessionStorage.getItem(TOKEN_KEY),
    currentUser() {
      try { return JSON.parse(sessionStorage.getItem(USER_KEY)) || null; } catch (e) { return null; }
    },
    clearSession() {
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(USER_KEY);
    },

    async login(username, password) {
      const out = useMock()
        ? await MaiaMock.login(username, password)
        : await http("/auth/login", { method: "POST", body: { username, password } });
      sessionStorage.setItem(TOKEN_KEY, out.token);
      sessionStorage.setItem(USER_KEY, JSON.stringify(out.user));
      return out.user;
    },

    /* ── registros ── */
    async listRecords() {
      const out = useMock() ? await MaiaMock.listRecords() : await http("/records");
      return out.records;
    },

    getRecord(id) {
      return useMock() ? MaiaMock.getRecord(id) : http("/records/" + encodeURIComponent(id));
    },

    deleteRecord(id) {
      return useMock() ? MaiaMock.deleteRecord(id)
        : http("/records/" + encodeURIComponent(id), { method: "DELETE" });
    },

    /* ── análisis ── */
    analyze(file, age) {
      if (useMock()) return MaiaMock.analyze(file, age);
      const fd = new FormData();
      fd.append("file", file);
      if (age != null) fd.append("chronological_age", String(age)); // opcional: el backend la detecta del EDF
      return http("/predict", {
        method: "POST", body: fd, isForm: true, timeoutMs: CFG.analyzeTimeoutMs
      });
    },

    analyzeDemo(demoId) {
      if (useMock()) return MaiaMock.analyzeDemo(demoId);
      return http("/predict-demo", {
        method: "POST", body: { demo_id: demoId }, timeoutMs: CFG.analyzeTimeoutMs
      });
    },

    /* ── señal EEG por ventana (envolvente min-máx, nunca la señal cruda) ── */
    getSignal(id, startS, durationS, points) {
      if (useMock()) return MaiaMock.getSignal(id, startS, durationS, points);
      const q = `?start_s=${startS}&duration_s=${durationS}&points=${points}`;
      return http("/records/" + encodeURIComponent(id) + "/signal" + q);
    }
  };
})();
