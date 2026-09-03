"""Pipeline de análisis: EDF real → detalle completo del contrato de la API.

Flujo (el mismo que documentó la Entrega 1):
  1. cargar EDF y validar canal Fpz-Cz;
  2. hipnograma anotado si viene, si no YASA;
  3. recortar la vigilia: ventana = sueño ± 30 min;
  4. épocas NREM → PSD (Welch) → espectro del panel + features;
  5. features de arquitectura del sueño desde el hipnograma;
  6. modelo → edad cerebral → BAI; norma espectral por edad.
"""
import re
from datetime import datetime, timezone

import numpy as np
from scipy.signal import welch
from scipy.interpolate import interp1d

from .. import config
from . import edf_io, staging, norms

BANDS = {"delta": (0.5, 4), "theta": (4, 8), "alpha": (8, 12),
         "sigma": (12, 16), "beta": (16, 25)}


class NoSleepDetected(edf_io.InvalidFile):
    pass


def _epoch_psd(x: np.ndarray, sfreq: float):
    """PSD de Welch de una época (µV²/Hz)."""
    nper = min(1024, len(x))
    f, p = welch(x, fs=sfreq, nperseg=nper, noverlap=nper // 2)
    return f, p


def _mean_psd(sig: np.ndarray, epoch_idx: list[int], sfreq: float, epoch_samples: int):
    acc = None
    f = None
    for i in epoch_idx:
        x = sig[i * epoch_samples:(i + 1) * epoch_samples]
        if len(x) < epoch_samples:
            continue
        f, p = _epoch_psd(x, sfreq)
        acc = p if acc is None else acc + p
    if acc is None:
        return None, None
    return f, acc / len(epoch_idx)


_trapz = getattr(np, "trapezoid", np.trapz)  # numpy 1.x / 2.x


def _band_powers(freqs: np.ndarray, psd: np.ndarray, prefix: str) -> dict:
    out = {}
    m_all = (freqs >= 0.5) & (freqs <= 25)
    total = _trapz(psd[m_all], freqs[m_all])
    for name, (lo, hi) in BANDS.items():
        m = (freqs >= lo) & (freqs < hi)
        abs_p = float(_trapz(psd[m], freqs[m]))
        out[f"{prefix}_{name}_abs"] = abs_p
        out[f"{prefix}_{name}_rel"] = float(abs_p / total) if total > 0 else 0.0
    return out


def run_analysis(psg_path: str, hyp_path: str | None, *, file_name: str, size_mb: float | None,
                 chronological_age: int, sex: str | None, subject_code: str | None,
                 predictor) -> tuple[dict, dict, np.ndarray, float]:
    """Devuelve (summary_sin_id, detail_sin_summary, señal_ventana_µV, sfreq)."""
    raw, n_channels = edf_io.load_raw(psg_path)
    sfreq = float(raw.info["sfreq"])
    epoch_samples = int(config.EPOCH_S * sfreq)
    total_s = raw.n_times / sfreq

    # ── hipnograma ──
    # El modelo EXIGE hipnograma anotado. Se midió: sobre SC4001E0, con anotación da
    # 24,8 años y con etapas estimadas por YASA da 46,2 — 21 años de diferencia, el
    # doble del MAE del modelo. La causa es que %N3, eficiencia y minutos_despierto
    # son features que entran directas al modelo, y las de un estadificador automático
    # no son las que vio al entrenar. Un número plausible y equivocado es peor que un
    # error, así que se rechaza.
    if not hyp_path:
        raise edf_io.InvalidFile(
            "Este registro no incluye hipnograma. El modelo de edad cerebral se entrenó "
            "con hipnogramas anotados por expertos y sus características de arquitectura "
            "del sueño dependen de ellos, así que estimarlos automáticamente daría un "
            "resultado poco fiable. Cargue un .zip con el par PSG + hipnograma "
            "(…-PSG.edf y …-Hypnogram.edf).")
    stages_full = staging.from_annotations(hyp_path, total_s)
    staging_source = "annotated"

    sleep_idx = np.where((stages_full >= 1) & (stages_full <= 4))[0]
    if len(sleep_idx) < 20:  # < 10 min de sueño
        raise NoSleepDetected("No se detectó un periodo de sueño analizable en el registro.")

    # ── bloque principal de sueño ──
    # Los registros Sleep Cassette cubren el día completo y puede haber siestas o
    # micro-episodios de somnolencia (frecuentes con estadificación automática).
    # Solo las rachas de ≥ 4 épocas seguidas de sueño (2 min) anclan el bloque;
    # los bloques separados por > 1 h de vigilia se separan y se analiza el mayor.
    is_sleep = (stages_full >= 1) & (stages_full <= 4)
    anchors = []
    run = 0
    for i, s in enumerate(is_sleep):
        run = run + 1 if s else 0
        if run == 4:
            anchors.extend(range(i - 3, i + 1))
        elif run > 4:
            anchors.append(i)
    if not anchors:
        anchors = [int(i) for i in sleep_idx]
    segments, cur = [], [anchors[0]]
    for i in anchors[1:]:
        if i - cur[-1] > 120:  # hueco > 60 min
            segments.append(cur)
            cur = [i]
        else:
            cur.append(i)
    segments.append(cur)
    main = max(segments, key=len)
    first_sleep, last_sleep = main[0], main[-1]

    # ── ventana de sueño: bloque principal ± 30 min (criterio de la Entrega 1) ──
    n_epochs_full = len(stages_full)
    w0 = max(0, first_sleep - config.MARGIN_EPOCHS)
    w1 = min(n_epochs_full, last_sleep + 1 + config.MARGIN_EPOCHS)
    w1 = min(w1, int(raw.n_times // epoch_samples))  # no pasarse de la señal real
    st_win = stages_full[w0:w1].copy()
    n_win = len(st_win)

    sig = raw.get_data(start=w0 * epoch_samples, stop=w1 * epoch_samples)[0] * 1e6  # µV
    del raw  # liberar memoria del registro completo

    unscored_ct = int(np.sum(st_win == -1))
    st_display = np.where(st_win < 0, 0, st_win).astype(int)

    # ── espectro NREM ──
    nrem_idx = [int(i) for i in np.where((st_win >= 1) & (st_win <= 3))[0]]
    if len(nrem_idx) < 10:
        raise NoSleepDetected("Muy pocas épocas NREM utilizables para calcular el espectro.")
    sampled = sorted({nrem_idx[int(k)] for k in np.linspace(0, len(nrem_idx) - 1, config.SPECTRUM_WINDOWS)})
    f_raw, psd_raw = _mean_psd(sig, sampled, sfreq, epoch_samples)

    grid = np.round(np.arange(config.FREQ_GRID_START, config.FREQ_GRID_STOP + 1e-9,
                              config.FREQ_GRID_STEP), 1)
    psd_grid = interp1d(f_raw, psd_raw, bounds_error=False, fill_value="extrapolate")(grid)
    psd_grid = np.maximum(psd_grid, 1e-4)

    # ── features espectrales (NREM y por estadio) ──
    features = _band_powers(grid, psd_grid, "nrem")
    for st_code, name in ((2, "n2"), (3, "n3"), (4, "rem")):
        idx = [int(i) for i in np.where(st_win == st_code)[0]]
        if len(idx) >= 5:
            pick = sorted({idx[int(k)] for k in np.linspace(0, len(idx) - 1, min(20, len(idx)))})
            fs_, ps_ = _mean_psd(sig, pick, sfreq, epoch_samples)
            g = interp1d(fs_, ps_, bounds_error=False, fill_value="extrapolate")(grid)
            features.update(_band_powers(grid, np.maximum(g, 1e-4), name))

    # ── features de arquitectura (dentro del bloque principal de sueño) ──
    sp0, sp1 = first_sleep, last_sleep + 1
    period = stages_full[sp0:sp1]
    n_period = len(period)
    tst_ep = int(np.sum((period >= 1) & (period <= 4)))
    features.update({
        "tst_min": tst_ep * config.EPOCH_S / 60.0,
        "sleep_efficiency": tst_ep / n_period if n_period else 0.0,
        "waso_min": int(np.sum(period == 0)) * config.EPOCH_S / 60.0,
        "pct_n1": float(np.sum(period == 1)) / max(tst_ep, 1),
        "pct_n2": float(np.sum(period == 2)) / max(tst_ep, 1),
        "pct_n3": float(np.sum(period == 3)) / max(tst_ep, 1),
        "pct_rem": float(np.sum(period == 4)) / max(tst_ep, 1),
    })
    rem_first = np.where(period == 4)[0]
    features["rem_latency_min"] = float(rem_first[0]) * config.EPOCH_S / 60.0 if len(rem_first) else 120.0

    # ── norma por edad y husos ──
    nrm = norms.build(grid, psd_grid, chronological_age)
    features["spindle_amp"] = nrm["subject_spindle_amp"]

    # ── modelo ──
    # El paquete edad_cerebral extrae sus propias 32 características del archivo:
    # tienen que ser exactamente las del entrenamiento, y las de arriba son las
    # que alimentan los paneles del tablero, que son otras.
    brain_age, meta, model_features = predictor.predict(psg_path, hyp_path)
    brain_age = round(float(brain_age), 1)
    bai = round(brain_age - chronological_age, 1)
    err = meta["typical_error"]

    # ── metadatos de reloj y calidad ──
    start_clock_s = _clock_seconds(psg_path, w0 * config.EPOCH_S)
    window_s = n_win * config.EPOCH_S
    pre_h = w0 * config.EPOCH_S / 3600.0
    post_h = max(total_s - (w0 + n_win) * config.EPOCH_S, 0.0) / 3600.0
    unscored_h = unscored_ct * config.EPOCH_S / 3600.0

    m = re.match(r"^SC4(\d\d)(\d)", file_name, re.I)
    subject_night = f"Sujeto {m.group(1)} · noche {m.group(2)}" if m else (subject_code or file_name)
    subject_code = subject_code or (f"SC{m.group(1)}" if m else file_name.split(".")[0][:8].upper())

    summary = {
        "subject_code": subject_code,
        "file_name": file_name,
        "sex": sex,
        "chronological_age": chronological_age,
        "brain_age": brain_age,
        "bai": bai,
        "over_threshold": abs(bai) > config.THRESHOLD_YEARS,
        "model_version": meta["version"],
        "staging_source": staging_source,
    }
    detail = {
        "threshold_years": config.THRESHOLD_YEARS,
        "interval": {
            "level": meta["interval_level"],
            "typical_error": err,
            "low": round(brain_age - err, 1),
            "high": round(brain_age + err, 1),
        },
        "spectrum": {
            "freqs": [float(v) for v in grid],
            "subject": _r(psd_grid),
            "norm": _r(nrm["norm"]),
            "norm_band_low": _r(nrm["norm_band_low"]),
            "norm_band_high": _r(nrm["norm_band_high"]),
            "spindle_band": list(config.SPINDLE_BAND),
            "spindle_deficit_pct": nrm["spindle_deficit_pct"],
            "spindle_age_corr_r": nrm["spindle_age_corr_r"],
            "marker_freq": nrm["marker_freq"],
        },
        "night": {
            "start_clock_s": start_clock_s,
            "window_s": window_s,
            "epoch_s": config.EPOCH_S,
            "stages": [int(s) for s in st_display],
        },
        "quality": {
            "composition": [
                {"label": "Vigilia previa", "hours": round(pre_h, 1), "kind": "wake"},
                {"label": "Ventana de sueño analizada",
                 "hours": round(window_s / 3600.0 - unscored_h, 1), "kind": "sleep"},
                {"label": "Sin clasificar", "hours": round(unscored_h, 1), "kind": "unscored"},
                {"label": "Vigilia posterior", "hours": round(post_h, 1), "kind": "wake"},
            ],
            "file": {
                "name": file_name,
                "size_mb": round(size_mb, 1) if size_mb else None,
                "total_duration_s": int(total_s),
                "sampling_hz": int(sfreq),
                "channels": n_channels,
                "channel_used": config.EEG_CHANNEL,
                "subject_night": subject_night,
            },
            "analysis": {
                "sleep_window_s": window_s,
                "epochs_in_window": n_win,
                "nrem_epochs_used": len(nrem_idx),
                "spectrum_windows": len(sampled),
                "epochs_discarded": n_win - len(nrem_idx),
                "unscored_pct": round(100.0 * unscored_ct / max(n_win, 1), 1),
                "wake_trimmed_s": int(max(total_s - window_s, 0)),
            },
        },
        # Las que entraron al modelo (las 32 del paquete), no las de los paneles:
        # si alguien audita una predicción, estas son las que la explican.
        "features": model_features,
        "features_panel": features,   # las del tablero (espectro, husos, arquitectura)
    }
    return summary, detail, sig, sfreq


def _r(arr) -> list[float]:
    return [round(float(v), 4) for v in arr]


def _clock_seconds(psg_path: str, offset_s: float) -> int:
    """Hora de reloj (segundos desde las 00:00) del inicio de la ventana."""
    import mne
    info = mne.io.read_raw_edf(psg_path, preload=False, verbose="ERROR").info
    meas = info.get("meas_date")
    if meas is None:
        return int(23 * 3600 + offset_s) % 86400
    if meas.tzinfo is not None:
        meas = meas.astimezone(timezone.utc).replace(tzinfo=None)
    day0 = meas.replace(hour=0, minute=0, second=0, microsecond=0)
    return int((meas - day0).total_seconds() + offset_s) % 86400
