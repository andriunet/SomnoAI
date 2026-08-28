/* ════════════════════════════════════════════════════════════════════
   MAIA · capa de gráficos (SVG puro, sin dependencias)
   Todas las funciones reciben DATOS (del contrato de la API) y un
   contenedor. Nada aquí conoce de dónde vienen los datos.
   ════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  /* ── utilidades compartidas ── */
  const S = (t, a = {}) => {
    const e = document.createElementNS("http://www.w3.org/2000/svg", t);
    for (const k in a) e.setAttribute(k, a[k]);
    return e;
  };
  const T = (a, txt) => Object.assign(S("text", a), { textContent: txt });
  const svg = (w, h) => S("svg", { viewBox: `0 0 ${w} ${h}`, role: "img" });
  const CV = n => getComputedStyle(document.body).getPropertyValue(n).trim();

  const nf = (v, d = 1) => v.toFixed(d).replace(".", ",");
  const sg = (v, d = 1) => (v > 0 ? "+" : "−") + nf(Math.abs(v), d);
  const pad2 = n => String(n).padStart(2, "0");
  const clockHM = s => pad2(Math.floor(s / 3600) % 24) + ":" + pad2(Math.floor(s / 60) % 60);
  const clockHMS = s => clockHM(s) + ":" + pad2(Math.round(s) % 60);
  const fmtHM = s => {
    const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60);
    return h > 0 ? `${h} h ${pad2(m)} min` : `${m} min`;
  };
  const fmtInt = n => n.toLocaleString("es-CO");
  const median = arr => {
    if (!arr.length) return 0;
    const a = [...arr].sort((x, y) => x - y), m = Math.floor(a.length / 2);
    return a.length % 2 ? a[m] : (a[m - 1] + a[m]) / 2;
  };

  window.MaiaUtil = { nf, sg, clockHM, clockHMS, fmtHM, fmtInt, median };

  const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

  /* ── tooltip flotante compartido (datos precisos al pasar el mouse) ── */
  const Tip = (() => {
    let el = null;
    const ensure = () => el || (el = Object.assign(
      document.body.appendChild(document.createElement("div")), { className: "tipbox" }));
    return {
      show(html, ev) {
        const t = ensure();
        t.innerHTML = html;
        let x = ev.clientX + 14, y = ev.clientY + 14;
        if (x + 290 > innerWidth) x = ev.clientX - 296;
        if (y + 100 > innerHeight) y = ev.clientY - 92;
        t.style.left = x + "px";
        t.style.top = y + "px";
        t.classList.add("on");
      },
      hide() { el && el.classList.remove("on"); }
    };
  })();

  /* convierte coordenadas del mouse al sistema del viewBox del SVG */
  const svgX = (svgEl, ev, vbWidth) => {
    const r = svgEl.getBoundingClientRect();
    return (ev.clientX - r.left) * (vbWidth / r.width);
  };

  /* Estadios: rampa ordinal de azules (claro = superficial); REM en otro tono */
  const STG = [
    { k: "W",   c: "#86b6ef" },
    { k: "N1",  c: "#5598e7" },
    { k: "N2",  c: "#2a78d6" },
    { k: "N3",  c: "#184f95" },
    { k: "REM", c: "#eb6834" }
  ];

  /* ── Distribución del BAI (vista Registros) ── */
  function renderStrip(el, records, TH) {
    const W = 1080, H = 96, L = 14, R = 14, pw = W - L - R, lo = -25, hi = 25;
    const s = svg(W, H);
    s.setAttribute("aria-label", "Distribución del BAI por registro");
    const x = v => L + ((Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo)) * pw;
    s.appendChild(S("rect", { x: L, y: 36, width: pw, height: 20, rx: 10, fill: CV("--surface-3") }));
    [[-25, -TH, "--younger"], [TH, 25, "--older"]].forEach(([a, b, c]) =>
      s.appendChild(S("rect", { x: x(a), y: 36, width: x(b) - x(a), height: 20, rx: 10, fill: CV(c), "fill-opacity": .20 })));
    [-20, -10, 0, 10, 20].forEach(t => {
      s.appendChild(S("line", { x1: x(t), x2: x(t), y1: 30, y2: 62, stroke: t === 0 ? CV("--ink2") : CV("--axis"),
        "stroke-width": t === 0 ? 1.5 : 1, "stroke-dasharray": t === 0 ? "none" : "3 3" }));
      s.appendChild(T({ x: x(t), y: 78, "text-anchor": "middle", "class": "tick" }, t === 0 ? "0" : sg(t, 0)));
    });
    records.forEach((r, i) => {
      const over = Math.abs(r.bai) > TH, pos = r.bai > 0;
      const c = S("circle", { cx: x(r.bai), cy: 46, r: over ? 6 : 5,
        fill: CV(over ? (pos ? "--older" : "--younger") : "--muted"),
        "fill-opacity": over ? 1 : .5, stroke: CV("--surface-1"), "stroke-width": 2,
        style: `--i:${Math.min(i, 18)}` }); // entrada escalonada de los puntos
      const dt = new Date(r.analyzed_at);
      c.addEventListener("mousemove", ev => Tip.show(
        `<span class="tt">${r.subject_code} · ${r.file_name}</span>` +
        `Edad ${r.chronological_age} → cerebral <b>${nf(r.brain_age)}</b> años<br>` +
        `BAI <b>${sg(r.bai)}</b> · ${over ? "Priorizar" : "En rango"} · ` +
        `${dt.getDate()} ${MESES[dt.getMonth()]}`, ev));
      c.addEventListener("mouseleave", Tip.hide);
      s.appendChild(c);
    });
    s.appendChild(T({ x: L, y: 20, "class": "axlbl" }, "más joven de lo esperado"));
    s.appendChild(T({ x: W - R, y: 20, "text-anchor": "end", "class": "axlbl" }, "mayor de lo esperado"));
    s.appendChild(T({ x: L + pw / 2, y: 92, "text-anchor": "middle", "class": "axlbl" },
      `Brain Age Index (años) · umbral de priorización ±${TH}`));
    el.replaceChildren(s);
  }

  /* ── Escala del BAI con intervalo (hero de Resultados) ── */
  function renderScale(el, d) {
    const TH = d.threshold_years, bai = d.bai;
    const err = d.interval.typical_error;
    const W = 1080, H = 76, L = 10, R = 10, pw = W - L - R, lo = -25, hi = 25;
    const s = svg(W, H);
    s.setAttribute("aria-label", "Posición del BAI en la escala");
    const x = v => L + ((Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo)) * pw;
    const col = bai > 0 ? "--older" : "--younger";
    s.appendChild(S("rect", { x: L, y: 26, width: pw, height: 14, rx: 7, fill: CV("--surface-3") }));
    [[-25, -TH, "--younger"], [TH, 25, "--older"]].forEach(([a, b, c]) => {
      s.appendChild(S("rect", { x: x(a), y: 26, width: x(b) - x(a), height: 14, rx: 7, fill: CV(c), "fill-opacity": .20 }));
      s.appendChild(T({ x: (x(a) + x(b)) / 2, y: 36, "text-anchor": "middle", "font-size": "9.5",
        fill: CV("--muted"), "letter-spacing": ".04em" }, "priorizar"));
    });
    s.appendChild(S("rect", { x: x(bai - err), y: 23, width: Math.max(x(bai + err) - x(bai - err), 4), height: 20, rx: 10,
      fill: CV(col), "fill-opacity": .24, stroke: CV(col), "stroke-width": 1.2 }));
    const dot = S("circle", { cx: x(bai), cy: 33, r: 8, fill: CV(col), stroke: CV("--surface-1"), "stroke-width": 2.5 });
    dot.addEventListener("mousemove", ev => Tip.show(
      `<span class="tt">BAI ${sg(bai)} años</span>` +
      `Edad cerebral <b>${nf(d.brain_age)}</b> · cronológica ${d.chronological_age}<br>` +
      `Intervalo del ${Math.round(d.interval.level * 100)}%: ${nf(d.interval.low)} – ${nf(d.interval.high)} años`, ev));
    dot.addEventListener("mouseleave", Tip.hide);
    s.appendChild(dot);
    s.appendChild(S("line", { x1: x(0), x2: x(0), y1: 19, y2: 47, stroke: CV("--ink2"), "stroke-width": 1.5 }));
    s.appendChild(T({ x: x(0), y: 14, "text-anchor": "middle", "class": "dlbl" }, "sin desvío"));
    [[-20, "20 años más joven"], [20, "20 años mayor"]].forEach(([v, t]) =>
      s.appendChild(T({ x: x(v), y: 60, "text-anchor": "middle", "class": "tick" }, t)));
    // con BAI extremo la etiqueta iría sobre los rótulos del eje: se sube
    const edgeY = Math.abs(bai) > 15 ? 14 : 60;
    s.appendChild(T({ x: x(bai), y: edgeY, "text-anchor": "middle", "class": "dlbl" }, "BAI " + sg(bai)));
    s.appendChild(T({ x: L, y: 73, "class": "axlbl" },
      `Zona sombreada: umbral de priorización de ±${TH} años · barra clara: intervalo de predicción del ${Math.round(d.interval.level * 100)} %`));
    el.replaceChildren(s);
  }

  /* ── Espectro del sujeto vs. norma de su edad ── */
  function renderSpectrum(el, d) {
    const sp = d.spectrum;
    const W = 1080, H = 340, L = 60, R = 20, Tp = 16, B = 50, pw = W - L - R, ph = H - Tp - B;
    const s = svg(W, H);
    s.setAttribute("aria-label", "Espectro del sujeto frente a la norma de su edad");
    const fmin = sp.freqs[0], fmax = sp.freqs[sp.freqs.length - 1];
    const x = f => L + ((f - fmin) / (fmax - fmin)) * pw;
    // eje y logarítmico: dominio 0.1 … 1000 µV²/Hz
    const y = v => Tp + ph - ((Math.log10(Math.max(v, 0.101)) + 1) / 4) * ph;
    [0.1, 1, 10, 100, 1000].forEach(v => {
      s.appendChild(S("line", { x1: L, x2: W - R, y1: y(v), y2: y(v), stroke: CV("--grid") }));
      s.appendChild(T({ x: L - 9, y: y(v) + 4, "text-anchor": "end", "class": "tick" },
        v < 1 ? "0,1" : (v === 1000 ? "1.000" : String(v))));
    });
    [0, 5, 10, 15, 20, 25].forEach(f => {
      if (f < fmin) return;
      s.appendChild(S("line", { x1: x(f), x2: x(f), y1: Tp, y2: Tp + ph, stroke: CV("--grid") }));
      s.appendChild(T({ x: x(f), y: Tp + ph + 17, "text-anchor": "middle", "class": "tick" }, f));
    });
    // banda de husos
    const [b0, b1] = sp.spindle_band;
    s.appendChild(S("rect", { x: x(b0), y: Tp, width: x(b1) - x(b0), height: ph, fill: CV("--s1"), "fill-opacity": .07 }));
    s.appendChild(T({ x: (x(b0) + x(b1)) / 2, y: Tp + 12, "text-anchor": "middle", "class": "tick",
      "font-weight": "600" }, "husos de sueño"));
    // banda de la norma (rango del conjunto de entrenamiento)
    let up = "M", dn = "";
    sp.freqs.forEach((f, i) => { up += `${x(f).toFixed(1)} ${y(sp.norm_band_high[i]).toFixed(1)}${i < sp.freqs.length - 1 ? "L" : ""}`; });
    for (let i = sp.freqs.length - 1; i >= 0; i--) dn += `L${x(sp.freqs[i]).toFixed(1)} ${y(sp.norm_band_low[i]).toFixed(1)}`;
    s.appendChild(S("path", { d: up + dn + "Z", fill: CV("--muted"), "fill-opacity": .16 }));
    // curvas
    const line = (vals, c, w, dash) => {
      let dd = "M";
      sp.freqs.forEach((f, i) => { dd += `${x(f).toFixed(1)} ${y(vals[i]).toFixed(1)}${i < sp.freqs.length - 1 ? "L" : ""}`; });
      s.appendChild(S("path", { d: dd, fill: "none", stroke: CV(c), "stroke-width": w,
        "stroke-dasharray": dash || "none", "stroke-linejoin": "round" }));
    };
    line(sp.norm, "--muted", 2, "6 4");
    line(sp.subject, "--s1", 2.4);
    // marcador de divergencia en la banda de husos
    const mi = sp.freqs.reduce((best, f, i) => Math.abs(f - sp.marker_freq) < Math.abs(sp.freqs[best] - sp.marker_freq) ? i : best, 0);
    const deficit = sp.spindle_deficit_pct;
    const mcol = deficit >= 0 ? "--older" : "--good";
    s.appendChild(S("line", { x1: x(sp.freqs[mi]), x2: x(sp.freqs[mi]), y1: y(sp.subject[mi]), y2: y(sp.norm[mi]),
      stroke: CV(mcol), "stroke-width": 2.2 }));
    s.appendChild(S("circle", { cx: x(sp.freqs[mi]), cy: y(sp.subject[mi]), r: 4.5, fill: CV(mcol),
      stroke: CV("--surface-1"), "stroke-width": 1.5 }));
    const lblX = Math.min(x(sp.freqs[mi]) + 46, W - R - 180);
    s.appendChild(T({ x: lblX, y: y(sp.norm[mi]) + 2, "class": "dlbl", fill: CV(mcol), "font-size": "12.5" },
      `${Math.abs(Math.round(deficit))} % ${deficit >= 0 ? "menos" : "más"} de husos`));
    s.appendChild(T({ x: L + pw / 2, y: H - 8, "text-anchor": "middle", "class": "axlbl" },
      "Frecuencia (Hz) · ondas lentas ← → ondas rápidas"));
    s.appendChild(T({ x: L - 44, y: Tp + ph / 2, "class": "axlbl", transform: `rotate(-90 ${L - 44} ${Tp + ph / 2})`,
      "text-anchor": "middle" }, "Potencia (µV²/Hz)"));

    // crosshair interactivo: frecuencia y potencias exactas bajo el cursor
    const xh = S("g", { "class": "xhair", opacity: 0 });
    const vln = S("line", { y1: Tp, y2: Tp + ph, stroke: CV("--axis"), "stroke-dasharray": "3 3" });
    const cS = S("circle", { r: 4.5, fill: CV("--s1"), stroke: CV("--surface-1"), "stroke-width": 1.5 });
    const cN = S("circle", { r: 3.5, fill: CV("--muted"), stroke: CV("--surface-1"), "stroke-width": 1.5 });
    xh.append(vln, cS, cN);
    s.appendChild(xh);
    const fmtP = v => v >= 10 ? nf(v, 1) : nf(v, 2);
    const capt = S("rect", { x: L, y: Tp, width: pw, height: ph, fill: "transparent", "class": "capt" });
    capt.addEventListener("mousemove", ev => {
      const fx = svgX(s, ev, W);
      const f = Math.max(fmin, Math.min(fmax, fmin + ((fx - L) / pw) * (fmax - fmin)));
      const i = Math.max(0, Math.min(sp.freqs.length - 1,
        Math.round((f - sp.freqs[0]) / (sp.freqs[1] - sp.freqs[0]))));
      const X = x(sp.freqs[i]);
      vln.setAttribute("x1", X); vln.setAttribute("x2", X);
      cS.setAttribute("cx", X); cS.setAttribute("cy", y(sp.subject[i]));
      cN.setAttribute("cx", X); cN.setAttribute("cy", y(sp.norm[i]));
      xh.setAttribute("opacity", 1);
      const inBand = sp.freqs[i] >= b0 && sp.freqs[i] <= b1;
      Tip.show(`<span class="tt">${nf(sp.freqs[i], 1)} Hz${inBand ? " · banda de husos" : ""}</span>` +
        `Este sujeto: <b>${fmtP(sp.subject[i])}</b> µV²/Hz<br>` +
        `Norma a su edad: ${fmtP(sp.norm[i])} µV²/Hz`, ev);
    });
    capt.addEventListener("mouseleave", () => { xh.setAttribute("opacity", 0); Tip.hide(); });
    s.appendChild(capt);
    el.replaceChildren(s);
  }

  /* ── Composición del registro (calidad) ── */
  function renderQuality(el, d) {
    const kindCol = { wake: "--surface-3", sleep: "--s1", unscored: "--warn" };
    const kindInv = { wake: 0, sleep: 1, unscored: 0 };
    const segs = d.quality.composition;
    const W = 1080, H = 110, L = 10, R = 10, pw = W - L - R;
    const s = svg(W, H);
    s.setAttribute("aria-label", "Composición del registro");
    const tot = segs.reduce((a, v) => a + v.hours, 0);
    let cx = L;
    segs.forEach(seg => {
      const w = (seg.hours / tot) * pw, c = kindCol[seg.kind] || "--surface-3", inv = kindInv[seg.kind] || 0;
      const rect = S("rect", { x: cx, y: 26, width: Math.max(w - 2, 1), height: 32, rx: 5, fill: CV(c),
        "class": "qseg" });
      rect.addEventListener("mousemove", ev => Tip.show(
        `<span class="tt">${seg.label}</span>` +
        `<b>${fmtHM(seg.hours * 3600)}</b> · ${nf(100 * seg.hours / tot, 1)} % del archivo`, ev));
      rect.addEventListener("mouseleave", Tip.hide);
      s.appendChild(rect);
      if (w > 110) {
        s.appendChild(T({ x: cx + w / 2, y: 40, "text-anchor": "middle", "font-size": "11.5", "font-weight": "600",
          fill: inv ? "#fff" : CV("--ink2") }, seg.label));
        s.appendChild(T({ x: cx + w / 2, y: 53, "text-anchor": "middle", "font-size": "11",
          fill: inv ? "#fff" : CV("--muted") }, nf(seg.hours) + " h"));
      }
      cx += w;
    });
    s.appendChild(T({ x: L, y: 16, "class": "axlbl" }, `Cómo se reparten las ${fmtHM(tot * 3600)} del archivo`));
    const colw = pw / segs.length;
    segs.forEach((seg, i) => {
      const lx = L + i * colw, c = kindCol[seg.kind] || "--surface-3";
      s.appendChild(S("rect", { x: lx, y: 68, width: 10, height: 10, rx: 3, fill: CV(c),
        stroke: CV("--border"), "stroke-width": 1 }));
      s.appendChild(T({ x: lx + 16, y: 77, "class": "tick" }, `${seg.label} · ${nf(seg.hours)} h`));
    });
    s.appendChild(T({ x: L, y: 92, "class": "axlbl" },
      "Solo la ventana de sueño alimenta al modelo · el resto se descarta antes de calcular el espectro"));
    el.replaceChildren(s);
  }

  /* ── Visor de señal EEG ──
     Pide la envolvente min-máx a la API por ventana (nunca la señal cruda
     completa) y pinta las bandas de estadio desde night.stages.            */
  const SignalViewer = {
    detail: null, win: 1800, center: 2400, _token: 0,

    init(detail) {
      this.detail = detail;
      this.win = 1800;
      this.center = Math.min(2400, detail.night.window_s / 2);
      const set = document.getElementById("sigWin");
      [...set.children].forEach(b => b.removeAttribute("aria-pressed"));
      set.querySelector('[data-w="1800"]').setAttribute("aria-pressed", "true");
      this.render();
    },

    stageAt(t) {
      const st = this.detail.night.stages;
      return st[Math.max(0, Math.min(st.length - 1, Math.floor(t / this.detail.night.epoch_s)))];
    },

    clamp() {
      const WT = this.detail.night.window_s;
      this.center = Math.max(this.win / 2, Math.min(WT - this.win / 2, this.center));
    },

    setWindow(w) { this.win = w; this.render(); },
    step(dir) { this.center += dir * this.win; this.render(); },
    jumpTo(frac) { this.center = Math.max(0, Math.min(1, frac)) * this.detail.night.window_s; this.render(); },

    async render() {
      if (!this.detail) return;
      this.clamp();
      const my = ++this._token;
      const night = this.detail.night, EP = night.epoch_s, WT = night.window_s, T0 = night.start_clock_s;
      const t0 = this.center - this.win / 2, t1 = this.center + this.win / 2;
      const W = 1080, H = 248, L = 52, R = 14, Tp = 10, B = 52, TRK = 22, pw = W - L - R, ph = H - Tp - B - TRK;
      const points = Math.round(pw);

      const sigBox = document.getElementById("c-signal");
      sigBox.classList.add("loading");
      let env;
      try {
        env = await MaiaAPI.getSignal(this.detail.id, t0, this.win, points);
      } catch (e) { sigBox.classList.remove("loading"); return; }
      if (my !== this._token) return; // llegó tarde: hubo otra petición después
      sigBox.classList.remove("loading");

      const s = svg(W, H);
      s.setAttribute("aria-label", "Señal EEG del registro");
      const x = t => L + ((t - t0) / this.win) * pw;
      const amp = 150, y = v => Tp + ph / 2 - (v / amp) * (ph / 2);

      // bandas de estadio de fondo
      const e0 = Math.floor(t0 / EP), e1 = Math.ceil(t1 / EP), NEP = night.stages.length;
      for (let e = e0; e < e1; e++) {
        if (e < 0 || e >= NEP) continue;
        const a = Math.max(e * EP, t0), b = Math.min((e + 1) * EP, t1);
        s.appendChild(S("rect", { x: x(a), y: Tp, width: Math.max(x(b) - x(a), 0.6), height: ph,
          fill: STG[night.stages[e]].c, "fill-opacity": .17 }));
      }

      // eje y
      [-100, -50, 0, 50, 100].forEach(v => {
        s.appendChild(S("line", { x1: L, x2: W - R, y1: y(v), y2: y(v),
          stroke: CV("--grid"), "stroke-opacity": v === 0 ? 1 : .65 }));
        s.appendChild(T({ x: L - 8, y: y(v) + 4, "text-anchor": "end", "class": "tick" }, v));
      });

      // envolvente min-máx servida por la API
      const n = env.min.length;
      let d = "M";
      for (let i = 0; i < n; i++) {
        const px = L + (i / n) * pw, py = y(Math.max(-amp, Math.min(amp, env.max[i])));
        d += `${px.toFixed(1)} ${py.toFixed(1)}${i < n - 1 ? "L" : ""}`;
      }
      for (let i = n - 1; i >= 0; i--) {
        const px = L + (i / n) * pw, py = y(Math.max(-amp, Math.min(amp, env.min[i])));
        d += `L${px.toFixed(1)} ${py.toFixed(1)}`;
      }
      s.appendChild(S("path", { d: d + "Z", fill: CV("--ink2"), "fill-opacity": .72, stroke: "none" }));

      // pista de estadios (codificación secundaria: el color nunca va solo)
      const ty = Tp + ph + 8;
      let run = e0;
      for (let e = e0; e <= e1; e++) {
        if (e === e1 || (e < NEP && night.stages[e] !== night.stages[run])) {
          const a = Math.max(run * EP, t0), b = Math.min(e * EP, t1), w = x(b) - x(a);
          if (w > 0.5 && run >= 0 && run < NEP) {
            s.appendChild(S("rect", { x: x(a) + .5, y: ty, width: Math.max(w - 1, .5), height: TRK - 6, rx: 3,
              fill: STG[night.stages[run]].c }));
            if (w > 30) s.appendChild(T({ x: x(a) + w / 2, y: ty + 12, "text-anchor": "middle", "font-size": "10.5",
              "font-weight": "700", fill: "#fff" }, STG[night.stages[run]].k));
          }
          run = e;
        }
      }

      // eje x
      const nT = 6;
      for (let i = 0; i <= nT; i++) {
        const t = t0 + (i / nT) * this.win;
        s.appendChild(T({ x: x(t), y: H - 30, "text-anchor": "middle", "class": "tick" },
          this.win <= 120 ? clockHMS(T0 + t) : clockHM(T0 + t)));
      }
      s.appendChild(T({ x: L - 40, y: Tp + ph / 2, "class": "axlbl", "text-anchor": "middle",
        transform: `rotate(-90 ${L - 40} ${Tp + ph / 2})` }, "EEG Fpz-Cz (µV)"));
      s.appendChild(T({ x: L, y: H - 8, "class": "axlbl" },
        this.win <= 120 ? "Escala de detalle: se distingue la forma de onda época a época"
                        : "Trazo dibujado como envolvente mín-máx · reduzca la ventana para ver la onda"));

      // crosshair: hora exacta, estadio y amplitud bajo el cursor
      const xh = S("g", { "class": "xhair", opacity: 0 });
      const vln = S("line", { y1: Tp, y2: Tp + ph, stroke: CV("--ink2"), "stroke-dasharray": "3 3" });
      xh.appendChild(vln);
      s.appendChild(xh);
      const fmtClock = this.win <= 120 ? clockHMS : clockHM;
      const capt = S("rect", { x: L, y: Tp, width: pw, height: ph + TRK + 8, fill: "transparent", "class": "capt" });
      capt.addEventListener("mousemove", ev => {
        const fx = svgX(s, ev, W);
        const frac = Math.max(0, Math.min(1, (fx - L) / pw));
        const t = t0 + frac * this.win;
        const i = Math.max(0, Math.min(n - 1, Math.floor(frac * n)));
        const X = L + frac * pw;
        vln.setAttribute("x1", X); vln.setAttribute("x2", X);
        xh.setAttribute("opacity", 1);
        Tip.show(`<span class="tt">${fmtClock(T0 + t)} · ${STG[this.stageAt(t)].k}</span>` +
          `Amplitud: <b>${nf(env.min[i], 0)}</b> a <b>${nf(env.max[i], 0)}</b> µV`, ev);
      });
      capt.addEventListener("mouseleave", () => { xh.setAttribute("opacity", 0); Tip.hide(); });
      s.appendChild(capt);
      document.getElementById("c-signal").replaceChildren(s);

      // navegador de la noche (desde el hipnograma, sin pedir señal)
      const NW = 1080, NH = 54, NL = 52, NR = 14, npw = NW - NL - NR;
      const nav = svg(NW, NH);
      nav.setAttribute("aria-label", "Navegador de la noche");
      const nx = t => NL + (t / WT) * npw;
      const step = WT / npw;
      for (let i = 0; i < npw; i++) {
        const st = this.stageAt(i * step);
        nav.appendChild(S("rect", { x: NL + i, y: 14, width: 1.2, height: 22, fill: STG[st].c, "fill-opacity": .85 }));
      }
      nav.appendChild(S("rect", { x: nx(t0), y: 10, width: Math.max(nx(t1) - nx(t0), 3), height: 30, rx: 4,
        fill: CV("--ink"), "fill-opacity": .10, stroke: CV("--ink"), "stroke-width": 1.6 }));
      [0, 2, 4, 6, 8].forEach(h => {
        const t = h * 3600;
        if (t > WT) return;
        nav.appendChild(T({ x: nx(t), y: 50, "text-anchor": "middle", "class": "tick" }, clockHM(T0 + t)));
      });
      nav.appendChild(T({ x: NL - 8, y: 29, "text-anchor": "end", "class": "tick" }, "noche"));
      document.getElementById("c-nav").replaceChildren(nav);

      // barra de estado (con segundos cuando la ventana es corta)
      const fmt = this.win <= 120 ? clockHMS : clockHM;
      document.getElementById("sigNow").textContent = fmt(T0 + t0) + " – " + fmt(T0 + t1);
      const sgc = STG[this.stageAt(this.center)];
      const badge = document.getElementById("sigStg");
      badge.textContent = sgc.k;
      badge.style.background = sgc.c;
      document.getElementById("sigPrev").disabled = t0 <= 0.5;
      document.getElementById("sigNext").disabled = t1 >= WT - 0.5;
    }
  };

  window.MaiaCharts = { STG, renderStrip, renderScale, renderSpectrum, renderQuality, SignalViewer };
})();
