/* ════════════════════════════════════════════════════════════════════
   MAIA · backend SIMULADO (modo demo)
   ────────────────────────────────────────────────────────────────────
   Implementa exactamente el mismo contrato que la API real
   (docs/API_CONTRACT.md) pero dentro del navegador:
     - los registros se persisten en localStorage,
     - los resultados de "analizar" son datos sintéticos plausibles y
       deterministas (mismo archivo → mismo resultado),
     - la señal EEG y el hipnograma se generan al vuelo.
   Cuando exista la API real basta poner su URL en js/config.js;
   este archivo deja de usarse (puede quedarse: no estorba).
   ════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  const DB_KEY = "maia_db_v2"; // v2: semilla con archivos reales de Sleep-EDFx
  const delay = ms => new Promise(r => setTimeout(r, ms));
  const p2 = n => String(n).padStart(2, "0");
  const nowLocalISO = () => {
    const d = new Date();
    return `${d.getFullYear()}-${p2(d.getMonth() + 1)}-${p2(d.getDate())}` +
           `T${p2(d.getHours())}:${p2(d.getMinutes())}:${p2(d.getSeconds())}`;
  };

  /* RNG determinista sembrado por texto (mismo id → mismos datos) */
  function seedFrom(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  function mulberry32(seed) {
    let a = seed >>> 0;
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const gauss = rng => {
    let u = 0, v = 0;
    while (u === 0) u = rng();
    while (v === 0) v = rng();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  };

  /* ── semilla inicial: 14 análisis con archivos REALES de Sleep-EDFx ──
     Sujeto, archivo, edad y sexo verificados contra el índice del dataset
     (PhysioNet sleep-edfx · SC-subjects). La convención del nombre es
     SC4ssN: ss = sujeto, N = noche; la edad cerebral/BAI sigue siendo
     sintética (no hay modelo detrás del modo demo).                      */
  const SEED = [
    ["SC00", "SC4001E0-PSG.edf", "2026-08-20T14:32:00", "F", 33, 41.6],
    ["SC70", "SC4701E0-PSG.edf", "2026-08-20T11:05:00", "M", 89, 68.2],
    ["SC02", "SC4021E0-PSG.edf", "2026-08-19T16:44:00", "F", 26, 44.9],
    ["SC74", "SC4741E0-PSG.edf", "2026-08-19T10:18:00", "M", 92, 74.6],
    ["SC31", "SC4311E0-PSG.edf", "2026-08-19T09:02:00", "M", 54, 71.1],
    ["SC64", "SC4641E0-PSG.edf", "2026-08-18T15:27:00", "F", 85, 69.8],
    ["SC15", "SC4151E0-PSG.edf", "2026-08-18T12:51:00", "M", 31, 38.4],
    ["SC40", "SC4401E0-PSG.edf", "2026-08-18T09:33:00", "F", 67, 60.9],
    ["SC03", "SC4031E0-PSG.edf", "2026-08-17T17:12:00", "F", 26, 30.2],
    ["SC76", "SC4761E0-PSG.edf", "2026-08-17T13:40:00", "M", 90, 86.1],
    ["SC01", "SC4011E0-PSG.edf", "2026-08-17T10:06:00", "F", 33, 35.8],
    ["SC42", "SC4421E0-PSG.edf", "2026-08-16T18:20:00", "F", 69, 67.4],
    ["SC22", "SC4221E0-PSG.edf", "2026-08-16T14:55:00", "F", 56, 57.3],
    ["SC00", "SC4002E0-PSG.edf", "2026-08-16T09:47:00", "F", 33, 38.2]
  ];

  /* demos: noches reales del dataset; edad cerebral canónica del modo demo */
  const DEMOS = {
    SC4001E0: { subject: "SC00", file: "SC4001E0-PSG.edf", sex: "F", age: 33, brain: 41.6 },
    SC4701E0: { subject: "SC70", file: "SC4701E0-PSG.edf", sex: "M", age: 89, brain: 68.2 },
    SC4021E0: { subject: "SC02", file: "SC4021E0-PSG.edf", sex: "F", age: 26, brain: 44.9 }
  };

  const MODEL_VERSION = "gbm-v0.4";
  const TYPICAL_ERR = 6.1;
  const TH = (window.MAIA_CONFIG && window.MAIA_CONFIG.thresholdYears) || 10;

  function summarize(rec) {
    return { ...rec, over_threshold: Math.abs(rec.bai) > TH };
  }

  /* ── base de datos en localStorage ── */
  function loadDB() {
    try {
      const raw = localStorage.getItem(DB_KEY);
      if (raw) return JSON.parse(raw);
    } catch (e) { /* localStorage puede fallar en file:// con configuraciones raras */ }
    const records = SEED.map(([subject, file, at, sex, age, brain], i) => ({
      id: "seed-" + file.replace(/\.edf$/i, "") + "-" + i,
      subject_code: subject, file_name: file, analyzed_at: at, sex,
      chronological_age: age, brain_age: brain,
      bai: Math.round((brain - age) * 10) / 10,
      model_version: MODEL_VERSION,
      staging_source: "annotated",
      age_source: "dataset-index",
      size_mb: null
    }));
    const db = { records };
    saveDB(db);
    return db;
  }
  let _db = null;
  function db() { if (!_db) _db = loadDB(); return _db; }
  function saveDB(d) {
    try { localStorage.setItem(DB_KEY, JSON.stringify(d)); } catch (e) { /* modo efímero */ }
  }

  /* ── generación determinista del detalle a partir del resumen ── */
  function hypnogram(rng, nEpochs) {
    // ciclos de sueño plausibles: N1 → N2 → N3 (decrece) → N2 → REM (crece) → W
    const a = [];
    const push = (v, n) => { for (let i = 0; i < n && a.length < nEpochs; i++) a.push(v); };
    push(0, 4 + Math.floor(rng() * 5));
    let cycle = 0;
    while (a.length < nEpochs) {
      push(1, 4 + Math.floor(rng() * 5));
      push(2, 44 + Math.floor(rng() * 20));
      push(3, Math.max(4, Math.floor((46 - cycle * 11) * (0.7 + rng() * 0.6))));
      push(2, 22 + Math.floor(rng() * 20));
      push(4, Math.floor((22 + cycle * 8) * (0.7 + rng() * 0.6)));
      push(0, 3 + Math.floor(rng() * 6));
      cycle++;
    }
    return a.slice(0, nEpochs);
  }

  function buildDetail(rec) {
    const rng = mulberry32(seedFrom(rec.id));
    const age = rec.chronological_age, brain = rec.brain_age, bai = rec.bai;

    // noche
    const startClock = 22 * 3600 + 25 * 60 + Math.floor(rng() * 90) * 60;   // 22:25 – 23:55
    const windowS = Math.round((7.9 + rng() * 1.6) * 3600 / 30) * 30;       // 7,9 – 9,5 h
    const epochS = 30;
    const stages = hypnogram(rng, Math.round(windowS / epochS));

    // espectro: 1/f + campana de husos cuya amplitud cae con la edad
    const freqs = [];
    for (let f = 0.5; f <= 25.001; f += 0.2) freqs.push(Math.round(f * 10) / 10);
    const spindleAmpFor = a => Math.max(0.35, 3.4 - 0.033 * (a - 25));
    const normAmp = spindleAmpFor(age);
    // divergencia de husos ligada al BAI: BAI positivo → menos husos que la norma
    const deficit = Math.max(-45, Math.min(80, Math.round(12 + 4.2 * bai + gauss(rng) * 4)));
    const subjAmp = Math.max(0.15, normAmp * (1 - deficit / 100));
    const slopeN = 1.70 + 0.02 * gauss(rng), slopeS = slopeN - 0.05 + 0.04 * gauss(rng);
    const fpeak = 13.1 + rng() * 0.5;
    const normF = f => 180 * Math.pow(f, -slopeN) + normAmp * Math.exp(-Math.pow((f - 13.4) / 1.35, 2)) + 0.17;
    const subjF = f => 155 * Math.pow(f, -slopeS) + subjAmp * Math.exp(-Math.pow((f - fpeak) / 1.5, 2)) + 0.19;
    const norm = freqs.map(normF), subject = freqs.map(subjF);

    // calidad
    const totalH = 21 + rng() * 2;                       // 21 – 23 h de archivo
    const unscoredPct = Math.round((1.5 + rng() * 3) * 10) / 10;
    const wakeTrimH = totalH - windowS / 3600 - 0.6;
    const prevH = wakeTrimH * (0.42 + rng() * 0.16);
    const postH = wakeTrimH - prevH;
    const epochsWin = Math.round(windowS / epochS);
    const nremEpochs = stages.filter(s => s >= 1 && s <= 3).length;
    const nremUsable = Math.round(nremEpochs * (1 - unscoredPct / 100) * (0.93 + rng() * 0.05));
    // convención Sleep-EDFx: SC4ssN… → ss = sujeto, N = noche
    const fm = /^SC4(\d\d)(\d)/i.exec(rec.file_name);
    const subjectNight = fm ? `Sujeto ${fm[1]} · noche ${fm[2]}` : rec.subject_code;

    return {
      ...summarize(rec),
      threshold_years: TH,
      interval: {
        level: 0.90,
        typical_error: TYPICAL_ERR,
        low: Math.round((brain - TYPICAL_ERR) * 10) / 10,
        high: Math.round((brain + TYPICAL_ERR) * 10) / 10
      },
      spectrum: {
        freqs, subject, norm,
        norm_band_low: norm.map(v => v * 0.64),
        norm_band_high: norm.map(v => v * 1.55),
        spindle_band: [12, 16],
        spindle_deficit_pct: deficit,
        spindle_age_corr_r: -0.50,
        marker_freq: Math.round(fpeak * 10) / 10
      },
      night: { start_clock_s: startClock, window_s: windowS, epoch_s: epochS, stages },
      quality: {
        composition: [
          { label: "Vigilia previa", hours: Math.round(prevH * 10) / 10, kind: "wake" },
          { label: "Ventana de sueño analizada", hours: Math.round(windowS / 360) / 10, kind: "sleep" },
          { label: "Sin clasificar", hours: 0.6, kind: "unscored" },
          { label: "Vigilia posterior", hours: Math.round(postH * 10) / 10, kind: "wake" }
        ],
        file: {
          name: rec.file_name,
          size_mb: rec.size_mb || Math.round((47 + rng() * 12) * 10) / 10,
          total_duration_s: Math.round(totalH * 3600),
          sampling_hz: 100,
          channels: 7,
          channel_used: "EEG Fpz-Cz",
          subject_night: subjectNight
        },
        analysis: {
          sleep_window_s: windowS,
          epochs_in_window: epochsWin,
          nrem_epochs_used: nremUsable,
          spectrum_windows: 30,
          epochs_discarded: epochsWin - nremUsable,
          unscored_pct: unscoredPct,
          wake_trimmed_s: Math.round(wakeTrimH * 3600)
        }
      }
    };
  }

  /* ── señal sintética por estadio (misma receta de la maqueta) ── */
  function makeSigAt(detail) {
    const stages = detail.night.stages, EP = detail.night.epoch_s;
    const stAt = t => stages[Math.max(0, Math.min(stages.length - 1, Math.floor(t / EP)))];
    return function (t) {
      const st = stAt(t);
      const r = n => { const x = Math.sin(t * n + n * 7.13) * 43758.5453; return x - Math.floor(x) - 0.5; };
      if (st === 0) return 24 * Math.sin(2 * Math.PI * 10.2 * t) * (0.45 + 0.55 * Math.sin(2 * Math.PI * 0.31 * t))
                        + 15 * r(91.7) + 9 * Math.sin(2 * Math.PI * 23.4 * t);
      if (st === 1) return 21 * Math.sin(2 * Math.PI * 5.6 * t) + 10 * Math.sin(2 * Math.PI * 7.9 * t) + 12 * r(83.1);
      if (st === 2) {
        const sp = Math.exp(-Math.pow(((t % 17) - 8.5) / 0.5, 2));
        const kc = Math.exp(-Math.pow(((t % 43) - 21) / 0.6, 2));
        const md = 0.6 + 0.4 * Math.sin(2 * Math.PI * 0.041 * t);
        return md * (20 * Math.sin(2 * Math.PI * 3.1 * t)) + 30 * sp * Math.sin(2 * Math.PI * 13.3 * t)
             + 55 * kc * Math.sin(2 * Math.PI * 0.85 * t) + 11 * r(77.3);
      }
      if (st === 3) {
        const md = 0.5 + 0.5 * Math.sin(2 * Math.PI * 0.055 * t);
        return md * (48 * Math.sin(2 * Math.PI * 1.05 * t) + 21 * Math.sin(2 * Math.PI * 2.3 * t + 1.1)) + 13 * r(69.9);
      }
      return 15 * Math.sin(2 * Math.PI * 6.4 * t) + 9 * Math.sin(2 * Math.PI * 9.1 * t) + 13 * r(61.3);
    };
  }

  const detailCache = new Map();
  function getDetail(id) {
    if (!detailCache.has(id)) {
      const rec = db().records.find(r => r.id === id);
      if (!rec) return null;
      detailCache.set(id, buildDetail(rec));
    }
    return detailCache.get(id);
  }

  function newId(fileName) {
    return fileName.replace(/\.(edf|zip)$/i, "") + "-" + Date.now().toString(36);
  }

  function createRecord({ subject, file, sex, age, brain, sizeMb, stagingSource, ageSource }) {
    const rec = {
      id: newId(file),
      subject_code: subject,
      file_name: file,
      analyzed_at: nowLocalISO(),
      sex: sex || null,
      chronological_age: age,
      brain_age: Math.round(brain * 10) / 10,
      bai: Math.round((brain - age) * 10) / 10,
      model_version: MODEL_VERSION,
      staging_source: stagingSource,
      age_source: ageSource || "manual",
      size_mb: sizeMb || null
    };
    db().records.unshift(rec);
    saveDB(db());
    return rec;
  }

  /* ══════════════ interfaz pública (misma forma que la API real) ══════════════ */
  window.MaiaMock = {
    async login(username, password) {
      await delay(420);
      if (username === "superusuario" && password === "somnoai2026") {
        return { token: "demo-token", user: { name: "Superusuario", initials: "SU" } };
      }
      throw { code: "invalid_credentials", message: "Usuario o contraseña incorrectos." };
    },

    async listRecords() {
      await delay(230);
      return { records: db().records.map(summarize) };
    },

    async getRecord(id) {
      await delay(320);
      const d = getDetail(id);
      if (!d) throw { code: "not_found", message: "El registro no existe." };
      return d;
    },

    async analyze(file, age) {
      // edad opcional: como el backend real, se intenta leer del encabezado EDF
      // (campo de paciente, bytes 8–88: «X F X Female_33yr»)
      let ageSource = "manual", sex = null;
      if (age == null) {
        if (/\.edf$/i.test(file.name) && file.slice) {
          try {
            const head = await file.slice(8, 88).text();
            const m = /(\d{1,3})\s*yr/i.exec(head);
            if (m && +m[1] >= 1 && +m[1] <= 120) { age = +m[1]; ageSource = "edf-header"; }
            const p = head.trim().split(/\s+/);
            if (p[1] === "F" || p[1] === "M") sex = p[1];
          } catch (e) { /* sin encabezado legible */ }
        }
        if (age == null) {
          await delay(400);
          throw { code: "age_required",
            message: "El archivo no trae la edad en su encabezado (o es un .zip, que el modo demo no puede abrir): ingrese la edad cronológica manualmente." };
        }
      }
      await delay(2600); // el análisis real tarda: carga + estadificación + espectros
      const m = /^SC4(\d\d)\d/i.exec(file.name);
      const subject = m ? "SC" + m[1] : file.name.replace(/\.(edf|zip)$/i, "").slice(0, 8).toUpperCase();
      const rng = mulberry32(seedFrom(file.name + "|" + age));
      // BAI plausible con leve regresión a la media (jóvenes ligeramente +, mayores −)
      const bai = Math.max(-22, Math.min(22, gauss(rng) * 7.5 - 0.12 * (age - 59)));
      const rec = createRecord({
        subject, file: file.name, sex, age,
        brain: age + bai,
        sizeMb: file.size ? Math.round(file.size / 1048576 * 10) / 10 : null,
        stagingSource: /\.zip$/i.test(file.name) ? "annotated" : "auto",
        ageSource
      });
      return getDetail(rec.id);
    },

    async analyzeDemo(demoId) {
      await delay(1400);
      const d = DEMOS[demoId];
      if (!d) throw { code: "not_found", message: "Registro demo desconocido." };
      const rec = createRecord({
        subject: d.subject, file: d.file, sex: d.sex, age: d.age, brain: d.brain,
        sizeMb: null, stagingSource: "annotated", ageSource: "dataset-index"
      });
      return getDetail(rec.id);
    },

    async getSignal(id, startS, durationS, points) {
      await delay(90);
      const detail = getDetail(id);
      if (!detail) throw { code: "not_found", message: "El registro no existe." };
      const sigAt = makeSigAt(detail);
      const sub = durationS <= 120 ? 6 : 14;
      const min = new Array(points), max = new Array(points);
      for (let i = 0; i < points; i++) {
        const ta = startS + (i / points) * durationS, tb = startS + ((i + 1) / points) * durationS;
        let mn = Infinity, mx = -Infinity;
        for (let k = 0; k < sub; k++) {
          const v = sigAt(ta + (k / sub) * (tb - ta));
          if (v < mn) mn = v;
          if (v > mx) mx = v;
        }
        min[i] = Math.round(mn * 10) / 10;
        max[i] = Math.round(mx * 10) / 10;
      }
      return { start_s: startS, duration_s: durationS, points, unit: "µV", min, max };
    },

    async deleteRecord(id) {
      await delay(260);
      const recs = db().records;
      const i = recs.findIndex(r => r.id === id);
      if (i < 0) throw { code: "not_found", message: "El registro no existe." };
      recs.splice(i, 1);
      detailCache.delete(id);
      saveDB(db());
      return { deleted: id };
    },

    /* utilidades del modo demo */
    reset() { localStorage.removeItem(DB_KEY); _db = null; detailCache.clear(); }
  };
})();
