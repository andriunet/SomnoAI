"""Hipnograma: anotado (archivos *-Hypnogram.edf de Sleep-EDFx) o automático (YASA).

Codificación del contrato: 0=W, 1=N1, 2=N2, 3=N3, 4=REM. Internamente usamos
-1 para épocas sin clasificar / movimiento (solo existen en hipnogramas anotados).
"""
import numpy as np
import mne

from .. import config

_ANNOT_MAP = {
    "Sleep stage W": 0,
    "Sleep stage 1": 1,
    "Sleep stage 2": 2,
    "Sleep stage 3": 3,
    "Sleep stage 4": 3,   # R&K 3+4 → N3 (AASM)
    "Sleep stage R": 4,
    "Sleep stage ?": -1,
    "Movement time": -1,
}


def from_annotations(hyp_path: str, total_duration_s: float) -> np.ndarray:
    """Hipnograma por época de 30 s a partir del EDF+ de anotaciones."""
    ann = mne.read_annotations(hyp_path)
    n_epochs = int(np.ceil(total_duration_s / config.EPOCH_S))
    stages = np.full(n_epochs, -1, dtype=np.int16)
    for onset, duration, desc in zip(ann.onset, ann.duration, ann.description):
        code = _ANNOT_MAP.get(desc, -1)
        e0 = int(round(onset / config.EPOCH_S))
        e1 = int(round((onset + duration) / config.EPOCH_S))
        stages[max(0, e0):min(n_epochs, e1)] = code
    return stages


def auto_yasa(raw) -> np.ndarray:
    """Estadificación automática con YASA sobre el canal EEG (época de 30 s)."""
    import yasa  # import diferido: solo se paga si hace falta

    sls = yasa.SleepStaging(raw, eeg_name=config.EEG_CHANNEL)
    pred = sls.predict()
    if hasattr(pred, "as_int"):
        # yasa >= 0.7: objeto Hypnogram; as_int() usa 0=W,1=N1,2=N2,3=N3,4=REM
        arr = np.asarray(pred.as_int(), dtype=np.int16)
        return np.where((arr >= 0) & (arr <= 4), arr, 0).astype(np.int16)
    mapping = {"W": 0, "N1": 1, "N2": 2, "N3": 3, "R": 4}
    return np.array([mapping.get(p, 0) for p in pred], dtype=np.int16)


def yasa_available() -> bool:
    try:
        import yasa  # noqa: F401
        return True
    except Exception:
        return False
