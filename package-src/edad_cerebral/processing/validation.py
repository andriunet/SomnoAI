"""Validación de la entrada del modelo. Equivale al validation.py del Taller 5.

La entrada de este modelo no es una fila de una tabla de negocio: es un archivo
EDF. Se valida en dos sitios distintos, y por eso hay dos funciones:

  - `validate_inputs`  las 32 características ya extraídas (que estén todas y
                       sean numéricas)
  - las comprobaciones del propio archivo (canales presentes, amplitud en rango)
    viven en processing/edf.py, porque solo tienen sentido con el EDF delante.
"""
from typing import Any, Dict, List, Tuple

import numpy as np

from edad_cerebral.config.core import config


def validate_inputs(*, input_data: Dict[str, Any]) -> Tuple[Dict[str, float], List[str]]:
    """→ (características validadas, lista de errores). Sin excepciones: la API decide."""
    errores: List[str] = []
    limpias: Dict[str, float] = {}

    faltan = [c for c in config.modelo.columnas if c not in input_data]
    if faltan:
        errores.append(
            f"Faltan {len(faltan)} de las {len(config.modelo.columnas)} características: "
            f"{', '.join(faltan[:5])}{'…' if len(faltan) > 5 else ''}")

    for c in config.modelo.columnas:
        if c in faltan:
            continue
        try:
            v = float(input_data[c])
        except (TypeError, ValueError):
            errores.append(f"La característica {c} no es numérica: {input_data[c]!r}")
            continue
        if np.isinf(v):
            errores.append(f"La característica {c} es infinita.")
            continue
        limpias[c] = v   # los NaN pasan: el imputador del pipeline los resuelve

    return limpias, errores
