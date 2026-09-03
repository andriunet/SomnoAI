"""El pipeline completo: imputar → escalar → RidgeBAI.

Imputar y escalar van DENTRO del pipeline a propósito: así se ajustan solo con el
train de cada fold y no se filtra información de validación.
"""
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from edad_cerebral.config.core import config
from edad_cerebral.ridge_bai import RidgeBAI


def crear_pipeline(alpha: float | None = None, lam: float | None = None) -> Pipeline:
    return Pipeline([
        ("imputar", SimpleImputer(strategy="median")),
        ("escalar", StandardScaler()),
        ("ridge", RidgeBAI(alpha=config.modelo.alpha if alpha is None else alpha,
                           lam=config.modelo.lam if lam is None else lam)),
    ])


edad_cerebral_pipe = crear_pipeline()
