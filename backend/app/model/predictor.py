"""Predictor de edad cerebral — la costura entre la API y el modelo empaquetado.

El modelo NO vive aquí: viaja en el wheel `edad_cerebral`, que se instala como
dependencia (primera línea de backend/requirements.txt) y trae dentro su
artefacto entrenado y su propio preprocesamiento.

CÓMO ACTUALIZAR EL MODELO (equipo de modelado):
  1. reentrenar y reconstruir el wheel con Experimentos/Sebastian/04_empaquetamiento.ipynb
  2. dejar el .whl nuevo en model-pkg/
  3. apuntar a él la primera línea de backend/requirements.txt
  4. reconstruir la imagen
  Sin tocar este archivo ni ningún otro del backend.

El paquete recibe el ARCHIVO, no un vector de características: la extracción es
parte del modelo (así lo pide el Taller 5) y tiene que ser exactamente la del
entrenamiento. Por eso el EDF se lee dos veces por análisis — una el pipeline del
tablero para lo que pinta, y otra el paquete para lo que predice. Es deliberado:
mantiene separado lo que se muestra de lo que entra al modelo.
"""
import logging

from edad_cerebral import __version__ as _version_paquete
from edad_cerebral.predict import ArchivoInvalido, predecir_desde_edf  # noqa: F401

log = logging.getLogger("maia.model")

# El backend codifica las etapas como enteros (staging.py); el paquete usa las
# etiquetas del hipnograma de Sleep-EDFx.
_ETIQUETA = {0: "W", 1: "N1", 2: "N2", 3: "N3", 4: "REM", -1: "?"}


def active_version() -> str:
    """Versión del modelo que realmente está sirviendo (para /health)."""
    return f"edad-cerebral-{_version_paquete}"


def predict(psg_path: str, hyp_path: str | None = None, stages=None) -> tuple[float, dict, dict]:
    """→ (edad_cerebral, meta, caracteristicas).

    `stages` solo se usa cuando no hay hipnograma anotado: son las etapas que
    estimó el estadificador automático, y hay que pasarlas porque el paquete no
    sabe estadificar. El resultado en ese caso es menos fiable — el modelo se
    entrenó con hipnogramas anotados por expertos.
    """
    etapas = None
    if hyp_path is None:
        if stages is None:
            raise ValueError("Sin hipnograma hay que pasar las etapas estimadas.")
        etapas = [_ETIQUETA.get(int(s), "?") for s in stages]

    r = predecir_desde_edf(psg_path, hyp_path, etapas)
    meta = {
        "version": r["version"],
        "typical_error": r["error_tipico"],
        "interval_level": r["nivel_intervalo"],
    }
    return r["edad_cerebral"], meta, r["caracteristicas"]
