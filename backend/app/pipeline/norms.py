"""Norma espectral por edad para el panel «Espectro frente a la norma».

⚠ PROVISIONAL: la componente aperiódica (1/f) se ajusta al propio sujeto y la
amplitud del pico de husos esperada por edad usa una recta anclada en la
literatura (los husos decaen de forma ~lineal con la edad). El equipo de
modelado debe reemplazar `expected_spindle_amp` y las bandas por percentiles
EMPÍRICOS calculados sobre los sujetos de edad similar del conjunto de
entrenamiento (ver backend/README.md).
"""
import numpy as np

SPINDLE_CENTER, SPINDLE_WIDTH = 13.5, 1.4
BAND_LOW_FACTOR, BAND_HIGH_FACTOR = 0.60, 1.70
# Correlación potencia sigma vs. edad medida por el equipo en la Entrega 1
# sobre las 153 noches de Sleep Cassette (se recalcula con la tabla de features).
SPINDLE_AGE_CORR_R = -0.50


def aperiodic_fit(freqs: np.ndarray, psd: np.ndarray):
    """Ajuste lineal en log-log de la componente 1/f, excluyendo la banda sigma."""
    mask = (freqs >= 0.5) & (freqs <= 25.0) & ~((freqs > 11.0) & (freqs < 17.0))
    lf, lp = np.log10(freqs[mask]), np.log10(np.maximum(psd[mask], 1e-6))
    slope, intercept = np.polyfit(lf, lp, 1)
    return 10 ** (intercept + slope * np.log10(freqs))


def expected_spindle_amp(age: float) -> float:
    """Amplitud esperada del pico de husos (µV²/Hz) a una edad dada. PROVISIONAL,
    calibrada para que las noches demo reales den divergencias plausibles."""
    return float(max(0.30, 2.4 - 0.022 * (age - 25.0)))


def build(freqs: np.ndarray, subject_psd: np.ndarray, age: float) -> dict:
    ap = aperiodic_fit(freqs, subject_psd)
    bump_shape = np.exp(-((freqs - SPINDLE_CENTER) / SPINDLE_WIDTH) ** 2)

    sigma_mask = (freqs >= 12.0) & (freqs <= 16.0)
    residual = np.maximum(subject_psd - ap, 0.0)
    subj_amp = float(residual[sigma_mask].max()) if sigma_mask.any() else 0.0
    marker_freq = float(freqs[sigma_mask][np.argmax(residual[sigma_mask])]) if sigma_mask.any() else SPINDLE_CENTER

    norm_amp = expected_spindle_amp(age)
    norm = ap + norm_amp * bump_shape
    deficit_pct = int(round(100.0 * (1.0 - subj_amp / norm_amp)))
    deficit_pct = max(-95, min(95, deficit_pct))

    return {
        "norm": norm,
        "norm_band_low": norm * BAND_LOW_FACTOR,
        "norm_band_high": norm * BAND_HIGH_FACTOR,
        "spindle_deficit_pct": deficit_pct,
        "spindle_age_corr_r": SPINDLE_AGE_CORR_R,
        "marker_freq": round(marker_freq, 1),
        "subject_spindle_amp": subj_amp,
    }
