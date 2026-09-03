from edad_cerebral.config.core import config


def test_hay_32_columnas_y_no_se_repiten():
    cols = config.modelo.columnas
    assert len(cols) == 32
    assert len(set(cols)) == 32


def test_las_columnas_van_en_el_orden_del_modelo():
    """El pipeline recibe un array, no un DataFrame: el orden es parte del contrato."""
    cols = config.modelo.columnas
    assert cols[0] == "mix_potencia_total_log_FpzCz"
    assert cols[12] == "mix_potencia_total_log_PzOz"
    assert cols[-8:] == list(config.modelo.arquitectura)


def test_las_bandas_son_contiguas_y_cubren_el_rango():
    bordes = sorted(config.modelo.bandas.values())
    for (_, fin), (ini, _) in zip(bordes, bordes[1:]):
        assert fin == ini, "las bandas deben ser contiguas, sin huecos ni solapes"
    assert bordes[0][0] == config.modelo.rango_hz[0]
    assert bordes[-1][1] == config.modelo.rango_hz[1]
