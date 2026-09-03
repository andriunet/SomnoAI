"""Carga y validación de archivos PSG (.edf) y paquetes .zip (PSG + hipnograma)."""
import re
import tempfile
import zipfile
from pathlib import Path

import mne

from .. import config


class InvalidFile(Exception):
    """Archivo inutilizable; el mensaje se muestra al usuario tal cual."""


def extract_zip(zip_path: str) -> tuple[str, str | None, str]:
    """Devuelve (ruta_psg, ruta_hipnograma|None, nombre_psg) extrayendo a un tmpdir."""
    tmp = tempfile.mkdtemp(prefix="maia_zip_")
    try:
        with zipfile.ZipFile(zip_path) as z:
            # ignorar la basura que mete el Finder de macOS (__MACOSX/, ._archivo)
            names = [n for n in z.namelist()
                     if n.lower().endswith(".edf")
                     and "__macosx" not in n.lower()
                     and not Path(n).name.startswith("._")]
            psg = [n for n in names if "hypno" not in Path(n).name.lower()]
            hyp = [n for n in names if "hypno" in Path(n).name.lower()]
            if not psg:
                raise InvalidFile("El .zip no contiene ningún .edf de PSG.")
            psg_path = z.extract(psg[0], tmp)
            hyp_path = z.extract(hyp[0], tmp) if hyp else None
            return psg_path, hyp_path, Path(psg[0]).name
    except zipfile.BadZipFile as e:
        raise InvalidFile("El archivo .zip está dañado o no es un zip válido.") from e


def read_subject_header(psg_path: str) -> dict:
    """Edad y sexo desde el campo de paciente del encabezado EDF (bytes 8–88).

    Sleep-EDFx lo escribe como «X F X Female_33yr» / «X M X Male_89yr»:
    el sexo va en el segundo campo y la edad como NNyr. Devuelve
    {"age": int|None, "sex": "F"|"M"|None} sin cargar la señal.
    """
    age = sex = None
    try:
        with open(psg_path, "rb") as fh:
            fh.seek(8)
            patient = fh.read(80).decode("ascii", errors="ignore")
        parts = patient.split()
        if len(parts) >= 2 and parts[1] in ("F", "M"):
            sex = parts[1]
        m = re.search(r"(\d{1,3})\s*yr", patient, re.I)
        if m and 1 <= int(m.group(1)) <= 120:
            age = int(m.group(1))
    except OSError:
        pass
    return {"age": age, "sex": sex}


def load_raw(psg_path: str):
    """Lee el EDF, valida el canal EEG y devuelve (raw solo-EEG, n_canales_originales)."""
    try:
        raw = mne.io.read_raw_edf(psg_path, preload=False, verbose="ERROR")
    except Exception as e:
        raise InvalidFile(f"No se pudo leer el EDF: {e}") from e
    n_channels = len(raw.ch_names)
    faltan = [c for c in config.EEG_CHANNELS_MODELO if c not in raw.ch_names]
    if faltan:
        raise InvalidFile(
            f"El archivo no contiene {'el canal' if len(faltan) == 1 else 'los canales'} "
            f"«{'», «'.join(faltan)}» (canales presentes: {', '.join(raw.ch_names[:8])}…). "
            "El modelo de edad cerebral necesita los dos canales de EEG "
            f"({', '.join(config.EEG_CHANNELS_MODELO)}); SomnoAI analiza polisomnografías "
            "con la convención de Sleep-EDFx.")
    # Los paneles del tablero y el visor trabajan sobre un solo canal; el segundo
    # lo lee el paquete del modelo por su cuenta, desde el archivo.
    raw.pick([config.EEG_CHANNEL])
    raw.load_data(verbose="ERROR")
    return raw, n_channels
