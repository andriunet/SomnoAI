"""De una curva espectral a números. Viene del notebook 02_caracteristicas.

El cálculo es idéntico al del notebook, a propósito: cualquier diferencia aquí
movería las características respecto de aquellas con las que se ajustó el
escalador del modelo, y la predicción saldría corrida sin dar ningún error.
"""
from typing import Dict

import numpy as np
import pandas as pd
from scipy.signal import welch

from edad_cerebral.config.core import config


def espectro(senal_epoca: np.ndarray, fs: float):
    """Una época de 30 s → (frecuencias, energía en µV²/Hz)."""
    m = config.modelo
    frecs, psd = welch(senal_epoca, fs=fs, nperseg=int(m.nperseg_epocas * fs))
    return frecs, psd * m.escala_psd


def doce_numeros(curva: np.ndarray, frecs: np.ndarray) -> Dict[str, float]:
    """Una curva espectral → 12 números: potencia total, 5 bandas abs y rel, y SEF95."""
    m = config.modelo
    lo, hi = m.rango_hz
    mask = (frecs >= lo) & (frecs <= hi)
    total = curva[mask].sum()

    f = {"potencia_total_log": np.log10(total)}
    for nombre, (a, b) in m.bandas.items():
        p = curva[(frecs >= a) & (frecs < b)].sum()
        f[f"abs_{nombre}"] = np.log10(p)
        f[f"rel_{nombre}"] = p / total
    acum = np.cumsum(curva[mask])
    f["sef95"] = frecs[mask][np.argmax(acum >= 0.95 * acum[-1])]
    return f


def arquitectura(noche: pd.DataFrame) -> Dict[str, float]:
    """Cuenta épocas del hipnograma → 8 números. No usa la señal para nada."""
    m = config.modelo
    c = noche.stage.value_counts()
    dormido = sum(c.get(e, 0) for e in m.etapas_dormido)
    rem = noche[noche.stage == "REM"]

    arq = {
        "horas_dormidas": dormido * m.epoca_s / 3600,
        "eficiencia": dormido / len(noche),
        "minutos_despierto": c.get("W_sleep", 0) * m.epoca_s / 60,
        "minutos_hasta_rem": ((rem.inicio_s.min() - noche.inicio_s.iloc[0]) / 60
                              if len(rem) else np.nan),
    }
    for e in m.etapas_dormido:
        arq[f"pct_sueno_en_{e}"] = c.get(e, 0) / dormido * 100 if dormido else np.nan
    return arq
