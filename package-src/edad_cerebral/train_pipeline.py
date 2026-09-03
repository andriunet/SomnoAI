"""Entrena el artefacto que se empaqueta. Viene del notebook 03_modelo.

Reconstruye el experimento C a partir de las dos tablas de características y la
partición —ambas dentro del paquete— y **no guarda nada si las métricas no
reproducen las del reporte**. Misma disciplina que 01_particion: antes que un
artefacto silenciosamente distinto, un fallo ruidoso.

    python -m edad_cerebral.train_pipeline
"""
import json
from typing import Dict

import numpy as np
import pandas as pd

from edad_cerebral.config.core import DATASET_DIR, config
from edad_cerebral.pipeline import crear_pipeline
from edad_cerebral.processing.data_manager import save_pipeline

TOLERANCIA = 0.005   # las métricas del reporte están redondeadas a 2 decimales


def por_sujeto(ruta) -> pd.DataFrame:
    """Una fila por sujeto: se promedian sus noches.

    La unidad del proyecto es el sujeto, nunca la noche: las dos noches de una
    persona comparten etiqueta de edad y separarlas sería fuga.
    """
    n = pd.read_csv(ruta)
    cols = [c for c in n.columns if c not in ("subject", "night", "registro", "sex", "age")]
    return (n.groupby("subject").agg({**{c: "mean" for c in cols}, "age": "first"})
            .rename(columns={"age": "edad"}))


def tabla_de_modelado() -> pd.DataFrame:
    """Las dos tablas por canal → las 32 columnas + la edad."""
    m = config.modelo
    fpz = por_sujeto(DATASET_DIR / config.app_config.csv_fpz)
    pz = por_sujeto(DATASET_DIR / config.app_config.csv_pz)
    if not (fpz.index == pz.index).all() or not np.allclose(fpz.edad, pz.edad):
        raise ValueError("Las dos tablas de canal no describen los mismos sujetos.")

    partes = [tabla[[f"mix_{e}" for e in m.espectrales]].add_suffix(f"_{sufijo}")
              for (_, sufijo), tabla in zip(m.canales, (fpz, pz))]
    return pd.concat(partes + [fpz[m.arquitectura], fpz[["edad"]]], axis=1)


def run_training() -> Dict:
    m = config.modelo
    cols = m.columnas

    datos = tabla_de_modelado()
    split = json.loads((DATASET_DIR / config.app_config.particion).read_text())
    TV, TEST = split["train_validation_subject_ids"], split["test_subject_ids"]
    y_tv, y_test = datos.loc[TV, "edad"].values, datos.loc[TEST, "edad"].values
    pos = {s: i for i, s in enumerate(TV)}
    X_tv = datos.loc[TV, cols].values

    # validación cruzada agrupada por sujeto: cada uno lo predice un modelo que no lo vio
    oof = np.full(len(TV), np.nan)
    for f in split["cv_folds"]:
        itr = [pos[s] for s in f["train_subject_ids"]]
        iva = [pos[s] for s in f["val_subject_ids"]]
        oof[iva] = crear_pipeline().fit(X_tv[itr], y_tv[itr]).predict(X_tv[iva])

    modelo = crear_pipeline().fit(X_tv, y_tv)
    metricas = {
        "mae_train": float(np.mean(np.abs(modelo.predict(X_tv) - y_tv))),
        "mae_validacion": float(np.mean(np.abs(oof - y_tv))),
        "mae_test": float(np.mean(np.abs(modelo.predict(datos.loc[TEST, cols].values) - y_test))),
    }

    desvios = {k: (metricas[k], v) for k, v in m.metricas_esperadas.items()
               if abs(metricas[k] - v) > TOLERANCIA}
    if desvios:
        detalle = " · ".join(f"{k}: obtenido {o:.4f}, esperado {e}" for k, (o, e) in desvios.items())
        raise RuntimeError(
            "El entrenamiento NO reproduce las métricas del reporte, así que no se guarda el "
            f"artefacto. {detalle}. Revise las versiones de las librerías y las tablas de entrada.")

    ruta = save_pipeline(pipeline_to_persist=modelo)
    return {"metricas": metricas, "ruta": str(ruta), "n_desarrollo": len(TV),
            "n_test": len(TEST), "n_columnas": len(cols)}


if __name__ == "__main__":
    r = run_training()
    print(f"{r['n_desarrollo']} sujetos de desarrollo · {r['n_columnas']} columnas")
    for k, v in r["metricas"].items():
        print(f"  {k:16s} {v:.2f}")
    print(f"guardado en {r['ruta']}")
