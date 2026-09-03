"""Guardar y cargar el pipeline entrenado. Equivale al data_manager del Taller 5."""
from pathlib import Path

import joblib
from sklearn.pipeline import Pipeline

from edad_cerebral.config.core import TRAINED_MODEL_DIR, config


def save_pipeline(*, pipeline_to_persist: Pipeline, file_name: str | None = None) -> Path:
    """Guarda el pipeline y deja solo esa versión en trained/.

    Borrar las anteriores evita el fallo silencioso de servir un artefacto viejo
    cuando alguien cambia la VERSION pero no reconstruye.
    """
    name = file_name or config.app_config.archivo_modelo
    TRAINED_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for viejo in TRAINED_MODEL_DIR.glob("*.pkl"):
        if viejo.name != name:
            viejo.unlink()
    destino = TRAINED_MODEL_DIR / name
    joblib.dump(pipeline_to_persist, destino)
    return destino


def load_pipeline(*, file_name: str | None = None) -> Pipeline:
    name = file_name or config.app_config.archivo_modelo
    ruta = TRAINED_MODEL_DIR / name
    if not ruta.exists():
        raise FileNotFoundError(
            f"Falta el modelo entrenado en {ruta}. Se genera con "
            f"`python -m edad_cerebral.train_pipeline` (ver 04_empaquetamiento.ipynb).")
    return joblib.load(ruta)
