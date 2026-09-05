"""Norma espectral EMPÍRICA por edad, para el panel del tablero.

Reemplaza a la recta inventada que había antes. La norma que se dibuja es la
mediana del espectro NREM de los sujetos de edad más parecida, y la banda gris
son sus percentiles 10 y 90 — que es lo que el panel decía hacer y no hacía.

Los espectros salen de `datasets/espectros_nrem_FpzCz.csv`: el promedio de TODAS
las épocas NREM de cada noche de Sleep Cassette, calculado con los mismos
parámetros de Welch que usa el tablero para el sujeto, de modo que las dos
curvas sean comparables.

Solo se usan los 62 sujetos de DESARROLLO. La norma es visualización y no entra
al modelo, pero mantener el test intacto también aquí evita la objeción.
"""
import json
from functools import lru_cache
from typing import Dict

import numpy as np
import pandas as pd

from edad_cerebral.config.core import DATASET_DIR, config

VECINOS = 13          # k sujetos más cercanos en edad; el peor caso llega a 11 años
BANDA_BAJA, BANDA_ALTA = 10, 90      # percentiles de la banda
SIGMA_LO, SIGMA_HI = 12.0, 16.0      # banda de husos
EXCLUIR_PICO = (11.0, 17.0)          # se excluye del ajuste 1/f para no contaminarlo


@lru_cache(maxsize=1)
def _tabla():
    """→ (frecuencias, matriz sujetos×frecuencias, edades). Un sujeto por fila."""
    d = pd.read_csv(DATASET_DIR / config.app_config.csv_espectros)
    cols = [c for c in d.columns if c.startswith("f")and c != "fname"]
    freqs = np.array([float(c[1:]) for c in cols])

    split = json.loads((DATASET_DIR / config.app_config.particion).read_text())
    desarrollo = set(split["train_validation_subject_ids"])
    d = d[d.subject.isin(desarrollo)]

    # una fila por sujeto: sus dos noches se promedian, como en el modelado
    g = d.groupby("subject")
    espectros = g[cols].mean().values
    edades = g["age"].first().values.astype(float)
    return freqs, espectros, edades


def ajuste_aperiodico(freqs: np.ndarray, psd: np.ndarray) -> np.ndarray:
    """La componente 1/f, ajustada en log-log excluyendo la banda de husos."""
    m = ~((freqs > EXCLUIR_PICO[0]) & (freqs < EXCLUIR_PICO[1]))
    pend, corte = np.polyfit(np.log10(freqs[m]), np.log10(np.maximum(psd[m], 1e-6)), 1)
    return 10 ** (corte + pend * np.log10(freqs))


def altura_pico(freqs: np.ndarray, psd: np.ndarray) -> tuple[float, float]:
    """Altura del pico de husos sobre la línea 1/f, y a qué frecuencia está.

    Misma definición para el sujeto y para la norma: comparar dos cosas medidas
    de forma distinta es de donde salían los porcentajes sin sentido.
    """
    residuo = np.maximum(psd - ajuste_aperiodico(freqs, psd), 0.0)
    sm = (freqs >= SIGMA_LO) & (freqs <= SIGMA_HI)
    if not sm.any():
        return 0.0, (SIGMA_LO + SIGMA_HI) / 2
    return float(residuo[sm].max()), float(freqs[sm][np.argmax(residuo[sm])])


def norma_para_edad(edad: float, k: int = VECINOS) -> Dict:
    """Mediana y percentiles del espectro de los k sujetos de edad más parecida."""
    freqs, espectros, edades = _tabla()
    k = min(k, len(edades))
    vecinos = np.argsort(np.abs(edades - edad))[:k]
    sel = espectros[vecinos]

    picos_ref = np.array([altura_pico(freqs, s)[0] for s in sel])
    potencias_ref = np.array([potencia_sigma(freqs, s) for s in sel])
    return {
        "freqs": freqs,
        "picos_ref": picos_ref,
        "potencias_ref": potencias_ref,
        "mediana": np.median(sel, axis=0),
        "p_bajo": np.percentile(sel, BANDA_BAJA, axis=0),
        "p_alto": np.percentile(sel, BANDA_ALTA, axis=0),
        "pico_mediano": float(np.median(picos_ref)),
        "n_sujetos": int(k),
        "edad_min": float(edades[vecinos].min()),
        "edad_max": float(edades[vecinos].max()),
    }


@lru_cache(maxsize=1)
def correlacion_husos_edad() -> float:
    """r de Pearson entre la potencia de husos y la edad, sobre desarrollo.

    Antes era una constante escrita a mano (-0,50). Ahora se mide, y sobre la
    MISMA magnitud que usa el porcentaje del panel (la potencia de la banda), no
    sobre la altura del pico: si no, el panel mezclaría dos medidas distintas.

    El tablero ya no lo muestra —es jerga para su público— pero sigue en el
    contrato de la API por si el reporte lo necesita.
    """
    freqs, espectros, edades = _tabla()
    pot = np.array([potencia_sigma(freqs, s) for s in espectros])
    return float(np.corrcoef(pot, edades)[0, 1])


def potencia_sigma(freqs: np.ndarray, psd: np.ndarray) -> float:
    """Potencia media en la banda de husos (12-16 Hz).

    Es lo que el panel DIBUJA, y también la familia de características que usa el
    modelo (abs_sigma, rel_sigma). Antes se comparaba la altura del pico sobre la
    línea 1/f, que mide otra cosa: cuánto sobresale el bulto respecto del fondo
    del propio sujeto. Un sujeto con todo el espectro hundido podía tener el bulto
    en la media y el texto decía «más husos que el 46 %» mientras la línea azul
    iba por debajo de la gris en todo el gráfico. Medir lo que se ve evita eso.
    """
    m = (freqs >= SIGMA_LO) & (freqs <= SIGMA_HI)
    return float(psd[m].mean()) if m.any() else 0.0


def porcentaje_por_debajo(valor: float, referencia: np.ndarray) -> int:
    """Qué porcentaje del grupo de referencia queda por debajo del sujeto.

    Se usa esto y no un porcentaje sobre la mediana porque ese se rompe: la
    mediana cae de 2,9 a los 26 años a 0,10 a los 95, así que un sujeto mayor con
    husos normales daba «1000 % más». Sobre los 78 sujetos, 23 se salían del
    recorte de ±95 %. Este siempre cae entre 0 y 100, y se lee directo en el
    gráfico porque la banda gris es p10-p90.

    Aviso de granularidad: con 13 sujetos de referencia solo hay 14 valores
    posibles (0, 8, 15, 23, 31, 38, 46, 54, ...). No es ruido, es la resolución
    que dan 13 puntos.
    """
    if not len(referencia):
        return 50
    return int(round(100.0 * float((referencia < valor).mean())))
