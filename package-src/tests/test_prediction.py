"""Pruebas del modelo empaquetado."""
import json

import numpy as np
import pytest

from edad_cerebral import __version__
from edad_cerebral.config.core import DATASET_DIR, config
from edad_cerebral.predict import extraer_caracteristicas, make_prediction
from edad_cerebral.processing.edf import ArchivoInvalido
from edad_cerebral.train_pipeline import tabla_de_modelado


def test_predice_un_numero_plausible():
    fila = tabla_de_modelado().iloc[0]
    r = make_prediction(input_data={c: fila[c] for c in config.modelo.columnas})
    assert r["errors"] == []
    assert r["version"] == __version__
    assert 15.0 < r["predictions"][0] < 110.0


def test_reproduce_el_mae_del_reporte_sobre_el_test():
    """El artefacto servido tiene que ser el del reporte, no uno parecido."""
    datos = tabla_de_modelado()
    split = json.loads((DATASET_DIR / config.app_config.particion).read_text())
    test = split["test_subject_ids"]
    pred = [make_prediction(input_data=datos.loc[s, config.modelo.columnas].to_dict()
                            )["predictions"][0] for s in test]
    mae = float(np.mean(np.abs(np.array(pred) - datos.loc[test, "edad"].values)))
    assert abs(mae - config.modelo.metricas_esperadas["mae_test"]) < 0.005


def test_avisa_si_faltan_caracteristicas():
    r = make_prediction(input_data={"mix_sef95_FpzCz": 20.0})
    assert r["predictions"] is None
    assert r["errors"] and "Faltan" in r["errors"][0]


def test_avisa_si_una_caracteristica_no_es_numerica():
    fila = tabla_de_modelado().iloc[0]
    entrada = {c: fila[c] for c in config.modelo.columnas}
    entrada["eficiencia"] = "muy buena"
    r = make_prediction(input_data=entrada)
    assert r["predictions"] is None
    assert any("no es numérica" in e for e in r["errors"])


def test_las_caracteristicas_del_edf_coinciden_con_la_tabla(noche_real):
    """La prueba central del empaquetamiento.

    Extraer desde el EDF con el código del paquete tiene que dar exactamente las
    mismas columnas que produjo el notebook 02. Si no, el modelo estaría recibiendo
    en producción características distintas de aquellas con las que se ajustó su
    escalador, y devolvería un número plausible y equivocado.
    """
    import pandas as pd

    psg, hyp = noche_real
    obtenidas = extraer_caracteristicas(psg, hyp)

    fpz = pd.read_csv(DATASET_DIR / config.app_config.csv_fpz)
    pz = pd.read_csv(DATASET_DIR / config.app_config.csv_pz)
    fila_fpz = fpz[fpz.registro == "SC4001E0"].iloc[0]
    fila_pz = pz[pz.registro == "SC4001E0"].iloc[0]

    for e in config.modelo.espectrales:
        assert obtenidas[f"mix_{e}_FpzCz"] == pytest.approx(fila_fpz[f"mix_{e}"], abs=1e-9)
        assert obtenidas[f"mix_{e}_PzOz"] == pytest.approx(fila_pz[f"mix_{e}"], abs=1e-9)
    for a in config.modelo.arquitectura:
        assert obtenidas[a] == pytest.approx(fila_fpz[a], abs=1e-9)


def test_rechaza_un_archivo_que_no_es_edf(tmp_path):
    falso = tmp_path / "no-es-un-edf.edf"
    falso.write_bytes(b"esto no es un EDF")
    with pytest.raises(Exception):
        extraer_caracteristicas(str(falso), str(falso))
