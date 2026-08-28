/* ════════════════════════════════════════════════════════════════════
   MAIA · lógica de la aplicación (navegación, estado y render)
   ════════════════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  const { nf, sg, fmtHM, fmtInt, median } = MaiaUtil;
  const C = MaiaCharts;
  const CFG = window.MAIA_CONFIG;
  const $ = id => document.getElementById(id);

  let records = [];        // resúmenes (vista Registros)
  let current = null;      // detalle mostrado en vRes
  let filt = "all";
  let query = "";
  let selFile = null;      // archivo elegido en vUp

  const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ══════════════ tema (claro / oscuro) ══════════════ */
  const THEME_KEY = "maia_theme";
  const ICONS = {
    light: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2.4M12 19.1v2.4M2.5 12h2.4M19.1 12h2.4M5 5l1.7 1.7M17.3 17.3 19 19M19 5l-1.7 1.7M6.7 17.3 5 19"/></svg>',
    dark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.4 14.2A8.2 8.2 0 0 1 9.8 3.6a8.2 8.2 0 1 0 10.6 10.6Z"/></svg>'
  };

  function themeButtons() { return ["btnTheme", "btnThemeLogin"].map($).filter(Boolean); }

  function applyTheme(t, rerender = true) {
    document.documentElement.dataset.theme = t;
    localStorage.setItem(THEME_KEY, t);
    // el icono muestra a qué tema se cambiará
    themeButtons().forEach(b => { b.innerHTML = t === "dark" ? ICONS.light : ICONS.dark; });
    if (rerender) rerenderCharts(); // los SVG leen los colores al dibujarse
  }

  function rerenderCharts() {
    if (!$("vList").classList.contains("hidden") && records.length)
      C.renderStrip($("c-strip"), records, CFG.thresholdYears);
    if (!$("vRes").classList.contains("hidden") && current) {
      C.renderScale($("c-scale"), current);
      C.renderSpectrum($("c-spectrum"), current);
      C.renderQuality($("c-quality"), current);
      C.SignalViewer.render();
    }
  }

  applyTheme(localStorage.getItem(THEME_KEY)
    || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"), false);
  themeButtons().forEach(b => b.onclick = () =>
    applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));

  /* contador animado para los KPI numéricos (enteros y decimales) */
  function countUp(el, to, decimals = 0) {
    const fmt = v => decimals ? nf(v, decimals) : String(Math.round(v));
    if (reducedMotion || !(to > 0)) { el.textContent = fmt(to); return; }
    const t0 = performance.now(), dur = 520;
    const step = now => {
      const p = Math.min(1, (now - t0) / dur);
      el.textContent = fmt(to * (p * (2 - p))); // ease-out
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }

  /* ── formato de fechas ── */
  const MES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  const dShort = { format: d => `${d.getDate()} ${MES[d.getMonth()]} ${d.getFullYear()}` };
  const dLong = new Intl.DateTimeFormat("es-CO", { day: "numeric", month: "long", year: "numeric" });
  const dTime = new Intl.DateTimeFormat("es-CO", { hour: "2-digit", minute: "2-digit", hour12: false });
  const parseAt = iso => new Date(iso);
  const sameDay = (a, b) => a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();

  /* ── navegación entre vistas ── */
  function go(v) {
    ["vList", "vUp", "vRes"].forEach(id => $(id).classList.toggle("hidden", id !== v));
    document.querySelectorAll("nav button").forEach(b =>
      b.setAttribute("aria-selected", String(b.dataset.v === v || (v === "vRes" && b.dataset.v === "vList"))));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /* ══════════════ vista REGISTROS ══════════════ */
  function renderTiles() {
    const n = records.length;
    countUp($("tCount"), n);
    const subjects = new Set(records.map(r => r.subject_code)).size;
    $("tCountN").textContent = `${subjects} sujeto${subjects === 1 ? "" : "s"} distintos`;
    countUp($("tOver"), records.filter(r => Math.abs(r.bai) > CFG.thresholdYears).length);
    if (n) {
      const bais = records.map(r => r.bai);
      countUp($("tMed"), median(bais.map(Math.abs)), 1);
      $("tMedN").textContent = `años · rango ${sg(Math.min(...bais))} a ${sg(Math.max(...bais))}`;
      const last = [...records].sort((a, b) => parseAt(b.analyzed_at) - parseAt(a.analyzed_at))[0];
      const at = parseAt(last.analyzed_at), now = new Date(), yest = new Date(now - 864e5);
      $("tLast").textContent = sameDay(at, now) ? "Hoy" : sameDay(at, yest) ? "Ayer" : dShort.format(at);
      $("tLastN").textContent = `${last.subject_code} · ${dTime.format(at)}`;
    } else {
      $("tMed").textContent = "—"; $("tMedN").textContent = " ";
      $("tLast").textContent = "—"; $("tLastN").textContent = " ";
    }
  }

  function renderTable() {
    const TH = CFG.thresholdYears;
    const rows = records
      .filter(r => filt === "all" || Math.abs(r.bai) > TH)
      .filter(r => !query
        || r.subject_code.toLowerCase().includes(query)
        || r.file_name.toLowerCase().includes(query));
    $("cnt").textContent = `${rows.length} registro${rows.length === 1 ? "" : "s"}`;
    $("tb").replaceChildren(...rows.map((r, i) => {
      const tr = document.createElement("tr");
      tr.className = "anim";
      tr.style.setProperty("--i", Math.min(i, 12)); // entrada escalonada, tope de 12
      const pos = r.bai > 0, over = Math.abs(r.bai) > TH;
      tr.innerHTML = `<td class="l"><b>${r.subject_code}</b></td>
        <td class="l" style="color:var(--muted);font-size:12px">${r.file_name}</td>
        <td class="l" style="color:var(--muted)">${dShort.format(parseAt(r.analyzed_at))}</td>
        <td>${r.chronological_age}</td><td>${nf(r.brain_age)}</td>
        <td class="l"><b style="color:var(${pos ? "--older" : "--younger"})">${sg(r.bai)}</b></td>
        <td class="l">${over ? '<span class="pill x">Priorizar</span>'
                             : '<span class="pill ok">En rango</span>'}</td>
        <td style="text-align:right"><span class="actions">
          <button class="act del" title="Borrar registro" aria-label="Borrar registro">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor"
              stroke-width="2" stroke-linecap="round"><path d="M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m3 0v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m5 5v6m4-6v6"/></svg>
          </button><span class="act">→</span></span></td>`;
      tr.onclick = () => openRecord(r.id);
      tr.querySelector(".del").onclick = e => { e.stopPropagation(); askDelete(r); };
      return tr;
    }));
  }

  async function refreshList() {
    // skeleton mientras llega el primer listado
    if (!records.length) {
      $("cnt").textContent = "cargando…";
      $("tb").innerHTML = Array.from({ length: 4 }, () =>
        `<tr>${Array.from({ length: 8 }, (_, i) =>
          `<td class="${i < 3 ? "l" : ""}"><span class="skel" style="width:${i === 1 ? 120 : 52}px">&nbsp;</span></td>`
        ).join("")}</tr>`).join("");
    }
    try {
      records = await MaiaAPI.listRecords();
      records.sort((a, b) => parseAt(b.analyzed_at) - parseAt(a.analyzed_at));
      renderTiles();
      renderTable();
      C.renderStrip($("c-strip"), records, CFG.thresholdYears);
    } catch (e) {
      $("cnt").textContent = e.message || "No se pudo cargar el listado.";
    }
  }

  async function openRecord(id) {
    try {
      const d = await MaiaAPI.getRecord(id);
      showResult(d);
    } catch (e) {
      alert(e.message || "No se pudo abrir el registro.");
    }
  }

  /* ── borrado con confirmación (modal) ── */
  let toDelete = null;

  function askDelete(r) {
    toDelete = r;
    $("mText").innerHTML =
      `Se eliminará el análisis de <b>${r.subject_code}</b> ` +
      `(${r.file_name} · ${dShort.format(parseAt(r.analyzed_at))}) de la base de datos. ` +
      `Esta acción no se puede deshacer.`;
    $("modal").classList.remove("hidden");
    $("mCancel").focus();
  }

  function closeModal() {
    $("modal").classList.add("hidden");
    toDelete = null;
  }

  async function confirmDelete() {
    if (!toDelete) return;
    const btn = $("mConfirm"), orig = btn.textContent;
    btn.disabled = true;
    btn.innerHTML = '<span class="spin"></span>Borrando…';
    try {
      await MaiaAPI.deleteRecord(toDelete.id);
      closeModal();
      refreshList();
    } catch (e) {
      closeModal();
      alert(e.message || "No se pudo borrar el registro.");
    } finally {
      btn.disabled = false;
      btn.textContent = orig;
    }
  }

  $("mCancel").onclick = closeModal;
  $("mConfirm").onclick = confirmDelete;
  $("modal").addEventListener("click", e => { if (e.target === $("modal")) closeModal(); });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !$("modal").classList.contains("hidden")) closeModal();
  });

  /* ══════════════ vista RESULTADOS ══════════════ */
  function showResult(d) {
    current = d;
    const TH = d.threshold_years;

    // 1 · archivo
    $("resFileName").textContent = d.file_name;
    const at = parseAt(d.analyzed_at);
    const sexTxt = d.sex === "F" ? "mujer" : d.sex === "M" ? "hombre" : null;
    $("resFileMeta").textContent =
      `Analizado el ${dLong.format(at)}, ${dTime.format(at)} · ` +
      (sexTxt ? `${sexTxt}, ` : "") + `${d.chronological_age} años`;

    // 2 · hero
    $("resModel").textContent = "Modelo " + d.model_version;
    $("hero").classList.toggle("younger", d.bai < 0);
    $("resBrain").innerHTML = `${nf(d.brain_age)} <small>± ${nf(d.interval.typical_error)} años</small>`;
    $("resBrainN").textContent =
      `Intervalo de predicción del ${Math.round(d.interval.level * 100)} %: ${nf(d.interval.low)} – ${nf(d.interval.high)}`;
    $("resChron").innerHTML = `${d.chronological_age} <small>años</small>`;
    $("resChronN").textContent = {
      "edf-header": "Detectada del encabezado del EDF",
      "dataset-index": "Del índice del dataset (SC-subjects)",
      "manual": "Dato ingresado al cargar el archivo"
    }[d.age_source] || "Dato ingresado al cargar el archivo";
    $("resBai").textContent = sg(d.bai);
    $("resBai").style.color = `var(${d.bai > 0 ? "--older" : "--younger"})`;
    $("resBaiN").textContent = d.bai > 0 ? "años por encima" : "años por debajo";
    C.renderScale($("c-scale"), d);

    // alerta según umbral e intervalo
    const alertEl = $("resAlert");
    const over = Math.abs(d.bai) > TH;
    const includesChron = d.chronological_age >= d.interval.low && d.chronological_age <= d.interval.high;
    alertEl.classList.toggle("c", over);
    alertEl.classList.toggle("w", !over);
    alertEl.querySelector(".m").textContent = over ? "!" : "i";
    if (over) {
      $("resAlertTi").textContent = "Este registro supera el umbral de priorización.";
      $("resAlertTx").innerHTML =
        `Con un BAI de <b>${sg(d.bai)}</b> años, la divergencia supera el umbral de ±${TH} años. ` +
        `El registro queda marcado para revisión prioritaria por el especialista.`;
    } else if (includesChron) {
      $("resAlertTi").textContent = "El intervalo de predicción incluye la edad cronológica.";
      $("resAlertTx").innerHTML =
        `Con un error típico de ±${nf(d.interval.typical_error)} años, un BAI de ${sg(d.bai)} está dentro del rango ` +
        `esperable. Este registro <b>no</b> supera el umbral de priorización de ${TH} años.`;
    } else {
      $("resAlertTi").textContent = "Divergencia moderada.";
      $("resAlertTx").innerHTML =
        `El intervalo de predicción no incluye la edad cronológica, pero el BAI de ${sg(d.bai)} ` +
        `no supera el umbral de priorización de ±${TH} años.`;
    }

    // 3 · espectro
    $("legNorm").textContent = `Norma a los ${d.chronological_age} años`;
    C.renderSpectrum($("c-spectrum"), d);
    const sp = d.spectrum;
    $("spectrumMini").innerHTML =
      `Los <b>husos de sueño (${sp.spindle_band[0]}–${sp.spindle_band[1]} Hz)</b> se pierden con la edad: el análisis ` +
      `del equipo encontró una correlación de <b>r = ${sp.spindle_age_corr_r.toFixed(2).replace(".", ",").replace("-", "−")}</b> ` +
      `entre su potencia y la edad, sobre las 153 noches del subconjunto Sleep Cassette. Este sujeto tiene un ` +
      `<b>${Math.abs(Math.round(sp.spindle_deficit_pct))} % ${sp.spindle_deficit_pct >= 0 ? "menos" : "más"}</b> de husos ` +
      `de los que le corresponden.`;

    // 4 · señal
    $("stgSource").textContent = d.staging_source === "annotated"
      ? "Hipnograma anotado" : "Estadificación automática";
    C.SignalViewer.init(d);

    // 5 · calidad
    C.renderQuality($("c-quality"), d);
    const kv = (label, value) => {
      const div = document.createElement("div");
      div.className = "kv";
      div.innerHTML = `<span>${label}</span><span>${value}</span>`;
      return div;
    };
    const f = d.quality.file, a = d.quality.analysis;
    $("kvFile").replaceChildren(
      kv("Nombre", f.name),
      kv("Tamaño", f.size_mb != null ? nf(f.size_mb) + " MB" : "—"),
      kv("Duración total", fmtHM(f.total_duration_s)),
      kv("Frecuencia de muestreo", f.sampling_hz + " Hz"),
      kv("Canales en el archivo", f.channels),
      kv("Canal utilizado", f.channel_used),
      kv("Sujeto · noche", f.subject_night)
    );
    $("kvAnalysis").replaceChildren(
      kv("Ventana de sueño", fmtHM(a.sleep_window_s)),
      kv("Épocas de 30 s en la ventana", fmtInt(a.epochs_in_window)),
      kv("Épocas NREM utilizables", fmtInt(a.nrem_epochs_used)),
      kv("Ventanas muestreadas para el espectro", a.spectrum_windows),
      kv("Épocas descartadas", fmtInt(a.epochs_discarded)),
      kv("Épocas sin clasificar", nf(a.unscored_pct) + " %"),
      kv("Vigilia recortada", fmtHM(a.wake_trimmed_s))
    );

    go("vRes");
    refreshList(); // el nuevo análisis debe aparecer en el listado
  }

  /* ══════════════ vista ANALIZAR ══════════════ */
  function showErr(el, msg) { el.textContent = msg; el.classList.add("show"); }
  function hideErr(el) { el.classList.remove("show"); }

  let detected = null;   // {age, sex} detectados del archivo seleccionado, o null

  /* ── detección de edad/sexo en el navegador ──
     El encabezado EDF trae el campo de paciente en los bytes 8–88
     («X F X Female_33yr»). Para .zip se localiza el PSG en el directorio
     central del zip y se descomprimen solo sus primeros bytes.            */
  function parsePatientField(text) {
    const m = /(\d{1,3})\s*yr/i.exec(text);
    const age = m && +m[1] >= 1 && +m[1] <= 120 ? +m[1] : null;
    const p = text.trim().split(/\s+/);
    const sex = p[1] === "F" || p[1] === "M" ? p[1] : null;
    return age != null ? { age, sex } : null;
  }

  async function peekEdf(blob) {
    return parsePatientField(await blob.slice(8, 88).text());
  }

  async function peekZip(file) {
    const dv = b => new DataView(b);
    // 1 · End Of Central Directory (firma 0x06054b50) en los últimos 64 KB
    const tailBuf = await file.slice(Math.max(0, file.size - 65558), file.size).arrayBuffer();
    const tail = dv(tailBuf);
    let eocd = -1;
    for (let i = tail.byteLength - 22; i >= 0; i--) {
      if (tail.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
    }
    if (eocd < 0) return null;
    const cdSize = tail.getUint32(eocd + 12, true);
    const cdOfs = tail.getUint32(eocd + 16, true);
    // 2 · directorio central: elegir el PSG (evitando hipnogramas y __MACOSX)
    const cd = dv(await file.slice(cdOfs, cdOfs + cdSize).arrayBuffer());
    const td = new TextDecoder();
    let p = 0, best = null;
    while (p + 46 <= cd.byteLength && cd.getUint32(p, true) === 0x02014b50) {
      const method = cd.getUint16(p + 10, true);
      const compSize = cd.getUint32(p + 20, true);
      const nameLen = cd.getUint16(p + 28, true);
      const extraLen = cd.getUint16(p + 30, true);
      const cmtLen = cd.getUint16(p + 32, true);
      const lho = cd.getUint32(p + 42, true);
      const name = td.decode(new Uint8Array(cd.buffer, p + 46, nameLen));
      const base = name.split("/").pop();
      if (/\.edf$/i.test(name) && !/__macosx/i.test(name) && !base.startsWith("._")) {
        const isPsg = !/hypno/i.test(base);
        if (!best || (isPsg && !best.isPsg)) best = { name, base, method, compSize, lho, isPsg };
      }
      p += 46 + nameLen + extraLen + cmtLen;
    }
    if (!best) return null;
    // 3 · encabezado local del elegido → inicio de sus datos
    const lh = dv(await file.slice(best.lho, best.lho + 30).arrayBuffer());
    if (lh.getUint32(0, true) !== 0x04034b50) return null;
    const dataStart = best.lho + 30 + lh.getUint16(26, true) + lh.getUint16(28, true);
    const compChunk = await file.slice(dataStart, dataStart + Math.min(best.compSize || 4096, 4096)).arrayBuffer();
    let headBytes;
    if (best.method === 0) {                       // almacenado sin comprimir
      headBytes = new Uint8Array(compChunk).slice(0, 128);
    } else if (best.method === 8 && "DecompressionStream" in window) {   // deflate
      const stream = new Blob([compChunk]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
      const reader = stream.getReader();
      const parts = [];
      let got = 0;
      try {
        while (got < 128) {
          const { value, done } = await reader.read();
          if (done) break;
          parts.push(value); got += value.length;
        }
      } catch (e) { /* el flujo se corta al no darle el resto: ya tenemos el inicio */ }
      reader.cancel().catch(() => {});
      const joined = new Uint8Array(got);
      let o = 0; parts.forEach(a => { joined.set(a, o); o += a.length; });
      headBytes = joined;
    } else return null;
    if (headBytes.length < 88) return null;
    return parsePatientField(new TextDecoder("ascii").decode(headBytes.slice(8, 88)));
  }

  function validateUpload() {
    const raw = $("age").value.trim();
    const age = parseInt(raw, 10);
    // edad manual válida, o edad detectada del archivo, o zip que el backend resolverá
    const manualOk = raw !== "" && age >= 1 && age <= 120;
    const autoOk = raw === "" && (detected != null || (selFile && /\.zip$/i.test(selFile.name)));
    $("btnRun").disabled = !(selFile && (manualOk || autoOk));
  }

  async function setFile(file) {
    hideErr($("upErr"));
    if (!file) return;
    if (!/\.(edf|zip)$/i.test(file.name)) {
      showErr($("upErr"), "Formato no aceptado: cargue un archivo .edf o un .zip con el par PSG + hipnograma.");
      return;
    }
    if (/hypnogram/i.test(file.name) && /\.edf$/i.test(file.name)) {
      showErr($("upErr"), "Ese archivo es solo el hipnograma (las anotaciones de estadios, sin señal EEG). " +
        "Cargue el PSG (…-PSG.edf) o un .zip con el par PSG + hipnograma.");
      return;
    }
    if (file.size > CFG.maxUploadMB * 1048576) {
      showErr($("upErr"), `El archivo supera el límite de ${CFG.maxUploadMB} MB.`);
      return;
    }
    selFile = file;
    detected = null;
    const isZip = /\.zip$/i.test(file.name);
    const mb = (file.size / 1048576).toFixed(1).replace(".", ",") + " MB";
    $("fileSelName").textContent = file.name;
    $("fileSel").querySelector(".ic").textContent = isZip ? "ZIP" : "EDF";
    $("fileSelMeta").textContent = mb + " · leyendo encabezado…";
    $("fileSel").classList.remove("hidden");
    validateUpload();
    try {
      detected = isZip ? await peekZip(file) : await peekEdf(file);
    } catch (e) { detected = null; }
    if (selFile !== file) return; // cambiaron el archivo mientras se leía
    if (detected) {
      const sexTxt = detected.sex === "F" ? "mujer" : detected.sex === "M" ? "hombre" : null;
      $("fileSelMeta").textContent = `${mb} · edad detectada: ${detected.age} años` +
        (sexTxt ? ` (${sexTxt})` : "");
      $("age").placeholder = String(detected.age);
    } else {
      $("fileSelMeta").textContent = mb + (isZip
        ? " · edad no visible aquí — se detectará al analizar"
        : " · el encabezado no trae la edad: ingrésela manualmente");
      $("age").placeholder = isZip ? "auto" : "—";
    }
    validateUpload();
  }

  function clearFile() {
    selFile = null;
    detected = null;
    $("fileInput").value = "";
    $("fileSel").classList.add("hidden");
    $("age").placeholder = "auto";
    validateUpload();
  }

  async function runAnalyze() {
    const btn = $("btnRun"), original = btn.textContent;
    const raw = $("age").value.trim();
    const age = raw === "" ? null : parseInt(raw, 10);
    hideErr($("upErr"));
    btn.disabled = true;
    btn.innerHTML = '<span class="spin"></span>Analizando registro…';
    try {
      const d = await MaiaAPI.analyze(selFile, age);
      clearFile();
      $("age").value = "";
      showResult(d);
    } catch (e) {
      showErr($("upErr"), e.message || "El análisis falló. Intente de nuevo.");
    } finally {
      btn.textContent = original;
      validateUpload();
    }
  }

  async function runDemo(el) {
    const demoId = el.dataset.demo;
    el.classList.add("busy");
    const nm = el.querySelector(".mt"), orig = nm.textContent;
    nm.innerHTML = '<span class="spin"></span>Analizando registro…';
    try {
      const d = await MaiaAPI.analyzeDemo(demoId);
      showResult(d);
    } catch (e) {
      showErr($("upErr"), e.message || "El análisis del registro demo falló.");
    } finally {
      el.classList.remove("busy");
      nm.textContent = orig;
    }
  }

  /* ══════════════ sesión ══════════════ */
  function enterApp(user) {
    if (user) {
      $("userName").textContent = user.name || "Superusuario";
      $("userAv").textContent = user.initials || "SU";
    }
    $("vLogin").classList.add("hidden");
    $("appHeader").classList.remove("hidden");
    go("vList");
    refreshList();
  }

  function showLogin() {
    ["vList", "vUp", "vRes"].forEach(id => $(id).classList.add("hidden"));
    $("appHeader").classList.add("hidden");
    $("vLogin").classList.remove("hidden");
    window.scrollTo({ top: 0 });
  }

  async function doLogin() {
    hideErr($("loginErr"));
    const btn = $("btnIn"), orig = btn.textContent;
    btn.disabled = true;
    btn.innerHTML = '<span class="spin"></span>Ingresando…';
    try {
      const user = await MaiaAPI.login($("usr").value.trim(), $("pwd").value);
      enterApp(user);
    } catch (e) {
      showErr($("loginErr"), e.message || "No se pudo iniciar sesión.");
    } finally {
      btn.disabled = false;
      btn.textContent = orig;
    }
  }

  function doLogout() {
    MaiaAPI.clearSession();
    showLogin();
  }

  /* ══════════════ eventos ══════════════ */
  $("btnIn").onclick = doLogin;
  ["usr", "pwd"].forEach(id => $(id).addEventListener("keydown", e => { if (e.key === "Enter") doLogin(); }));
  $("btnOut").onclick = doLogout;
  window.addEventListener("maia:unauthorized", showLogin);

  document.querySelector("nav").onclick = e => {
    const b = e.target.closest("button[data-v]");
    if (b) go(b.dataset.v);
  };
  $("btnNew").onclick = () => go("vUp");
  $("btnOther").onclick = () => go("vUp");
  $("backUp").onclick = () => go("vList");
  $("backRes").onclick = () => go("vList");

  $("filt").onclick = e => {
    const b = e.target.closest("button");
    if (!b) return;
    [...e.currentTarget.children].forEach(c => c.setAttribute("aria-pressed", String(c === b)));
    filt = b.dataset.f;
    renderTable();
  };
  $("srch").addEventListener("input", e => { query = e.target.value.trim().toLowerCase(); renderTable(); });

  // carga de archivo: clic, selección y arrastre
  $("dz").onclick = () => $("fileInput").click();
  $("fileInput").addEventListener("change", e => setFile(e.target.files[0]));
  $("fileSelRm").onclick = clearFile;
  ["dragenter", "dragover"].forEach(ev => $("dz").addEventListener(ev, e => {
    e.preventDefault();
    $("dz").classList.add("over");
  }));
  ["dragleave", "drop"].forEach(ev => $("dz").addEventListener(ev, e => {
    e.preventDefault();
    $("dz").classList.remove("over");
  }));
  $("dz").addEventListener("drop", e => setFile(e.dataTransfer.files[0]));
  $("age").addEventListener("input", validateUpload);
  $("btnRun").onclick = runAnalyze;
  document.querySelectorAll(".filerow.demo").forEach(el => el.onclick = () => runDemo(el));

  // visor de señal
  $("sigWin").onclick = e => {
    const b = e.target.closest("button");
    if (!b) return;
    [...e.currentTarget.children].forEach(c => c.removeAttribute("aria-pressed"));
    b.setAttribute("aria-pressed", "true");
    C.SignalViewer.setWindow(+b.dataset.w);
  };
  $("sigPrev").onclick = () => C.SignalViewer.step(-1);
  $("sigNext").onclick = () => C.SignalViewer.step(1);
  $("c-nav").onclick = e => {
    const r = e.currentTarget.getBoundingClientRect();
    const frac = ((e.clientX - r.left) / r.width - 52 / 1080) / ((1080 - 52 - 14) / 1080);
    C.SignalViewer.jumpTo(frac);
  };

  /* ══════════════ arranque ══════════════ */
  if (MaiaAPI.isLoggedIn()) enterApp(MaiaAPI.currentUser());
  else showLogin();
})();
