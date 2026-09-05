"""Rutas de los EDF reales, si están disponibles.

Las pruebas que necesitan un EDF se saltan cuando el dataset no está montado: son
8 GB versionados con DVC, no viven en el repositorio. Las demás pruebas —config,
características, predicción sobre la tabla— no lo necesitan y siempre corren.
"""
import os
from pathlib import Path

import pytest

CODIGO = "SC4001E0"


def _dir_datos():
    env = os.getenv("SLEEP_EDF_DIR")
    if env and Path(env).is_dir():
        return Path(env)
    for p in [Path.cwd(), *Path.cwd().parents]:
        cand = p / "Microproyecto" / "Data" / "sleep-cassette"
        if cand.is_dir():
            return cand
    return None


@pytest.fixture(scope="session")
def noche_real():
    d = _dir_datos()
    if d is None:
        pytest.skip("dataset Sleep-EDF no disponible (defina SLEEP_EDF_DIR)")
    psg = d / f"{CODIGO}-PSG.edf"
    hyps = sorted(d.glob(f"{CODIGO[:6]}*-Hypnogram.edf"))
    if not psg.exists() or not hyps:
        pytest.skip(f"no se encontró {CODIGO} en {d}")
    return str(psg), str(hyps[0])
