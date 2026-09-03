"""Estimación de edad cerebral a partir del EEG de una polisomnografía.

Empaqueta el modelo del experimento C (los dos canales) descrito en
`Experimentos/Sebastian/README.md`: Ridge con corrección del sesgo del BAI,
32 columnas, MAE de validación cruzada 10,43 años.

    from edad_cerebral.predict import predecir_desde_edf
    r = predecir_desde_edf("SC4001E0-PSG.edf", "SC4001EC-Hypnogram.edf")
    r["edad_cerebral"]
"""
from pathlib import Path

# VERSION vive DENTRO del paquete: fuera de él no viajaría en el wheel.
with open(Path(__file__).resolve().parent / "VERSION", encoding="utf-8") as _f:
    __version__ = _f.read().strip()
