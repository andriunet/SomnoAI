"""Predicción: de un EDF a una edad cerebral.

La forma de `make_prediction` es la del Taller 6 — devuelve
{"predictions", "version", "errors"} — para que la API la consuma igual.

Se separan dos pasos porque la API los necesita por separado: extraer las 32
características de un archivo, y predecir a partir de ellas.

A diferencia del taller, el artefacto se carga de forma perezosa y no al importar
el módulo. Es necesario: `train_pipeline` importa este paquete para construir el
artefacto, y cargarlo al importar sería un círculo — no habría modelo todavía.
"""
import typing as t

from edad_cerebral import __version__ as _version
from edad_cerebral.config.core import config
from edad_cerebral.processing.data_manager import load_pipeline
from edad_cerebral.processing.edf import (  # noqa: F401  (se reexporta: la API la captura)
    ArchivoInvalido,
    cargar_noche,
    psds_de_la_noche,
    recortar,
)
from edad_cerebral.processing.features import arquitectura, doce_numeros
from edad_cerebral.processing.validation import validate_inputs

_pipe = None


def _pipeline():
    global _pipe
    if _pipe is None:
        _pipe = load_pipeline()
    return _pipe


def extraer_caracteristicas(psg_path: str, hyp_path: str) -> t.Dict[str, float]:
    """EDF + hipnograma → las 32 columnas que espera el modelo.

    Reproduce el notebook 02 para las columnas `mix_*` de los dos canales y las 8
    de arquitectura. No calcula las curvas por fase: el modelo no las usa.
    """
    raw, fs, epocas = cargar_noche(psg_path, hyp_path)
    noche = recortar(epocas)

    fila: t.Dict[str, float] = {}
    for canal, sufijo in config.modelo.canales:
        psds, frecs = psds_de_la_noche(raw, noche, fs, canal)
        for k, v in doce_numeros(psds.mean(0), frecs).items():
            fila[f"mix_{k}_{sufijo}"] = float(v)
    fila.update({k: float(v) for k, v in arquitectura(noche).items()})
    return fila


def make_prediction(*, input_data: t.Union[t.Dict[str, t.Any], "object"]) -> dict:
    """Las 32 características → edad cerebral. Misma forma que el Taller 6."""
    data = dict(input_data)
    validadas, errores = validate_inputs(input_data=data)
    resultado = {"predictions": None, "version": _version, "errors": errores}

    if not errores:
        X = [[validadas[c] for c in config.modelo.columnas]]
        resultado["predictions"] = [float(p) for p in _pipeline().predict(X)]
    return resultado


def predecir_desde_edf(psg_path: str, hyp_path: str) -> dict:
    """El camino completo, que es el que usa la API."""
    caracteristicas = extraer_caracteristicas(psg_path, hyp_path)
    r = make_prediction(input_data=caracteristicas)
    if r["errors"]:
        raise ArchivoInvalido("; ".join(r["errors"]))
    return {
        "edad_cerebral": r["predictions"][0],
        "caracteristicas": caracteristicas,
        "version": config.app_config.version_modelo,
        "error_tipico": config.modelo.mae_validacion,
        "nivel_intervalo": config.modelo.nivel_intervalo,
    }
