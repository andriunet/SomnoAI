"""Lectura del EDF y recorte de la noche. Viene del notebook 02_caracteristicas.

A diferencia del notebook, que buscaba los archivos por código con glob, aquí las
rutas llegan explícitas: quien llama (la API) ya las tiene.
"""
import numpy as np
import pandas as pd

from edad_cerebral.config.core import config


class ArchivoInvalido(ValueError):
    """El EDF no sirve para este modelo. El mensaje explica por qué."""


def cargar_noche(psg_path: str, hyp_path: str):
    """→ (raw, fs, épocas de 30 s con su etapa). Requiere hipnograma."""
    import mne
    mne.set_log_level("ERROR")

    m = config.modelo
    raw = mne.io.read_raw_edf(psg_path, preload=False)
    fs = raw.info["sfreq"]
    duracion = raw.n_times / fs

    faltan = [c for c, _ in m.canales if c not in raw.ch_names]
    if faltan:
        raise ArchivoInvalido(
            f"El registro no tiene el canal {', '.join(faltan)}. Este modelo necesita los "
            f"dos canales de EEG ({', '.join(c for c, _ in m.canales)}); el archivo trae: "
            f"{', '.join(raw.ch_names)}.")

    ann = mne.read_annotations(hyp_path)
    epocas = [{"inicio_s": o + m.epoca_s * k, "stage": m.etapas.get(d, "?")}
              for o, dur, d in zip(ann.onset, ann.duration, ann.description)
              for k in range(int(dur // m.epoca_s))
              if o + m.epoca_s * k + m.epoca_s <= duracion]   # descarta lo que no tiene señal
    if not epocas:
        raise ArchivoInvalido("El hipnograma no cubre ninguna época con señal.")
    return raw, fs, pd.DataFrame(epocas)


def recortar(epocas: pd.DataFrame) -> pd.DataFrame:
    """Del primer al último sueño. La W de dentro pasa a llamarse W_sleep."""
    dormido = epocas.stage.isin(config.modelo.etapas_dormido).values
    if not dormido.any():
        raise ArchivoInvalido("El hipnograma no marca ninguna época de sueño.")
    i, j = np.where(dormido)[0][[0, -1]]
    noche = epocas.iloc[i:j + 1].copy()
    noche["stage"] = noche.stage.replace({"W": "W_sleep"})
    if len(noche) < 2:
        raise ArchivoInvalido("La ventana de sueño es demasiado corta para analizarla.")
    return noche


def psds_de_la_noche(raw, noche: pd.DataFrame, fs: float, canal: str):
    """Un espectro por época válida de la ventana de sueño → (psds, frecuencias)."""
    from edad_cerebral.processing.features import espectro

    epoca_s = config.modelo.epoca_s
    ini = noche.inicio_s.iloc[0]
    fin = noche.inicio_s.iloc[-1] + epoca_s
    senal = raw.get_data(picks=[canal], start=int(ini * fs), stop=int(fin * fs))[0]

    verificar_amplitud(senal, canal)

    n = int(epoca_s * fs)
    psds, frecs = [], None
    for _, ep in noche.iterrows():
        d = int((ep.inicio_s - ini) * fs)
        trozo = senal[d:d + n]
        if len(trozo) == n:
            frecs, p = espectro(trozo, fs)
            psds.append(p)
    if not psds:
        raise ArchivoInvalido(f"No hay ninguna época completa de señal en {canal}.")
    return np.array(psds), frecs


def verificar_amplitud(senal: np.ndarray, canal: str) -> None:
    """Un EEG de sueño vive en un rango conocido de µV.

    Fuera de él, lo más probable es que el EDF declare las unidades de otra forma.
    Importa porque 10 de las 32 columnas son log10 de potencia: unas unidades
    distintas las desplazan una constante y el modelo devolvería un número
    plausible y equivocado, sin lanzar ningún error. Mejor rechazar.
    """
    lo, hi = config.modelo.amplitud_uv_esperada
    p99 = float(np.percentile(np.abs(senal), 99)) * 1e6      # V → µV
    if not (lo <= p99 <= hi):
        raise ArchivoInvalido(
            f"La amplitud de {canal} ({p99:.3g} µV en el percentil 99) está fuera del rango "
            f"esperable para un EEG ({lo:g}–{hi:g} µV). Probablemente el archivo declara las "
            f"unidades de otra forma; el modelo daría un resultado erróneo.")
