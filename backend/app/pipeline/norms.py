"""Norma espectral por edad para el panel «Espectro frente a la norma».

Adaptador fino sobre `edad_cerebral.norms`, que es donde vive el cálculo: la
norma se deriva del conjunto de entrenamiento, así que viaja con la versión del
modelo, no con el backend.

Qué se dibuja, y de dónde sale:
  - la línea gris  → mediana del espectro NREM de los 13 sujetos de desarrollo
                     de edad más parecida
  - la banda gris  → sus percentiles 10 y 90
  - el porcentaje  → qué fracción de ese grupo tiene MENOS potencia en 12-16 Hz
                     que el sujeto. Se mide sobre la potencia de la banda, que es
                     lo que el gráfico dibuja: con la altura del pico sobre la
                     línea 1/f el texto podía decir «más husos que el 46 %»
                     mientras la curva azul iba por debajo de la gris entera.

Antes esto era una recta con coeficientes elegidos a mano y una banda del 60 % y
170 % de esa recta. La recta erraba por un factor de 8 a los 95 años.
"""
import numpy as np

from edad_cerebral.norms import (
    altura_pico,
    correlacion_husos_edad,
    norma_para_edad,
    porcentaje_por_debajo,
    potencia_sigma,
)

SPINDLE_BAND = (12.0, 16.0)


def build(freqs: np.ndarray, subject_psd: np.ndarray, age: float) -> dict:
    ref = norma_para_edad(age)

    # Las dos rejillas vienen del mismo paso de 0,2 Hz, pero si alguna vez
    # divergen, mejor interpolar que dibujar curvas desalineadas en silencio.
    if len(ref["freqs"]) != len(freqs) or not np.allclose(ref["freqs"], freqs):
        interp = lambda y: np.interp(freqs, ref["freqs"], y)
        mediana, p_bajo, p_alto = map(interp, (ref["mediana"], ref["p_bajo"], ref["p_alto"]))
    else:
        mediana, p_bajo, p_alto = ref["mediana"], ref["p_bajo"], ref["p_alto"]

    subj_amp, marker_freq = altura_pico(freqs, subject_psd)
    pico_norma = ref["pico_mediano"]

    percentil = porcentaje_por_debajo(potencia_sigma(freqs, subject_psd), ref["potencias_ref"])
    deficit_pct = int(round(100.0 * (1.0 - subj_amp / pico_norma))) if pico_norma > 0 else 0
    deficit_pct = max(-95, min(95, deficit_pct))   # solo orientativo; el panel usa el percentil

    return {
        "norm": mediana,
        "norm_band_low": p_bajo,
        "norm_band_high": p_alto,
        "spindle_percentile": percentil,
        "spindle_deficit_pct": deficit_pct,
        "spindle_age_corr_r": round(correlacion_husos_edad(), 2),
        "marker_freq": round(marker_freq, 1),
        "subject_spindle_amp": subj_amp,
        # para el pie del panel: cuántos sujetos y de qué edades salió la banda
        "norm_n_subjects": ref["n_sujetos"],
        "norm_age_min": int(ref["edad_min"]),
        "norm_age_max": int(ref["edad_max"]),
    }
