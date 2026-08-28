"""Predictor de edad cerebral — punto de enchufe del modelo del equipo.

CÓMO ENCHUFAR EL MODELO REAL (equipo de modelado):
  Guardar en backend/model_artifacts/model.joblib un dict:
      {
        "model": <estimador sklearn ya entrenado, .predict(DataFrame)>,
        "feature_names": [columnas en el orden esperado],
        "meta": {
          "version": "gbm-v1.0",          # aparece en la píldora del tablero
          "typical_error": 8.3,           # semiancho del intervalo (años)
          "interval_level": 0.90
        }
      }
  Las features disponibles (nombres exactos) son las que produce
  pipeline/analysis.py y quedan en detail["features"] de cada análisis:
  bandas abs/rel por NREM y por estadio (nrem_delta_abs, n2_sigma_rel, …),
  arquitectura (pct_n1, sleep_efficiency, waso_min, tst_min, rem_latency_min,
  pct_n2, pct_n3, pct_rem) y spindle_amp.
  ¡La edad cronológica NO es una feature! (regla del proyecto).

Mientras no exista model.joblib se usa un HEURÍSTICO PROVISIONAL anclado en
las correlaciones que el equipo midió en la Entrega 1 (%N1 r=+0.64,
eficiencia r=−0.62, WASO r=+0.57, husos r=−0.50). Sirve para que el flujo
completo corra con datos reales; NO es el modelo de la entrega.
"""
import logging

from .. import config

log = logging.getLogger("maia.model")

_BUNDLE = None
_TRIED = False


def _load_bundle():
    global _BUNDLE, _TRIED
    if _TRIED:
        return _BUNDLE
    _TRIED = True
    path = config.MODEL_DIR / "model.joblib"
    if path.exists():
        import joblib
        _BUNDLE = joblib.load(path)
        log.info("Modelo del equipo cargado: %s", _BUNDLE["meta"]["version"])
    else:
        log.warning("model_artifacts/model.joblib no existe → heurístico provisional")
    return _BUNDLE


def predict(features: dict) -> tuple[float, dict]:
    """→ (edad_cerebral, meta). meta: version, typical_error, interval_level."""
    bundle = _load_bundle()
    if bundle is not None:
        import pandas as pd
        X = pd.DataFrame([[features.get(k, 0.0) for k in bundle["feature_names"]]],
                         columns=bundle["feature_names"])
        return float(bundle["model"].predict(X)[0]), dict(bundle["meta"])
    return _heuristic(features), {
        "version": "heuristic-v0 (provisional)",
        "typical_error": 10.2,      # MAE del Ridge de la Entrega 1
        "interval_level": 0.90,
    }


def _heuristic(f: dict) -> float:
    """Provisional: cada marcador de la Entrega 1 se mapea a un puntaje de
    envejecimiento acotado en [0,1] y la edad es una mezcla ponderada. Los
    pesos siguen las correlaciones medidas (%N1 +0.64, eficiencia −0.62,
    WASO +0.57, husos −0.50, N3 −0.42)."""
    clip = lambda v: max(0.0, min(1.0, v))
    s_spindle = clip(1.0 - f.get("spindle_amp", 1.2) / 2.0)     # husos: marcador dominante
    s_n3 = clip((0.20 - f.get("pct_n3", 0.12)) / 0.20)          # sueño profundo
    s_delta = clip((0.93 - f.get("nrem_delta_rel", 0.90)) / 0.10)
    s_n1 = clip((f.get("pct_n1", 0.08) - 0.05) / 0.15)
    s_frag = 0.5 * clip((0.95 - f.get("sleep_efficiency", 0.85)) / 0.30) \
           + 0.5 * clip((f.get("waso_min", 40.0) / 60.0) / 4.0)  # fragmentación

    score = (0.35 * s_spindle + 0.25 * s_n3 + 0.15 * s_delta
             + 0.15 * s_n1 + 0.10 * s_frag)
    return max(20.0, min(100.0, 27.0 + 58.0 * score))
