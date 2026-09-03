import numpy as np

from edad_cerebral.config.core import config
from edad_cerebral.processing.features import doce_numeros, espectro


def test_doce_numeros_da_doce_numeros():
    frecs = np.arange(0, 50.25, 0.25)
    f = doce_numeros(np.ones_like(frecs), frecs)
    assert len(f) == 12
    assert set(f) == set(config.modelo.espectrales)


def test_las_relativas_suman_uno():
    """Las cinco bandas cubren el rango entero, así que sus fracciones suman ~1."""
    frecs = np.arange(0, 50.25, 0.25)
    curva = np.random.default_rng(0).random(len(frecs)) + 0.1
    f = doce_numeros(curva, frecs)
    total = sum(f[f"rel_{b}"] for b in config.modelo.bandas)
    assert abs(total - 1.0) < 0.02   # el borde superior del rango entra en el total


def test_un_seno_domina_su_banda():
    """Una señal de 13 Hz debe concentrar su energía en sigma (12-16 Hz)."""
    fs = 100.0
    t = np.arange(0, 30, 1 / fs)
    frecs, psd = espectro(50e-6 * np.sin(2 * np.pi * 13 * t), fs)
    f = doce_numeros(psd, frecs)
    assert f["rel_sigma"] == max(f[f"rel_{b}"] for b in config.modelo.bandas)
