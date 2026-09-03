"""Configuración del backend MAIA / SomnoAI."""
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
DATA_DIR = BASE_DIR / "data"
DEMO_DIR = DATA_DIR / "demo"                               # EDFs de Sleep-EDFx
STORE_DIR = DATA_DIR / "store"                             # BD + señales derivadas
MODEL_DIR = BASE_DIR / "model_artifacts"                   # aquí enchufa el equipo su modelo

DB_PATH = STORE_DIR / "maia.db"

# Usuario único del prototipo (la maqueta define este acceso)
USERNAME = "superusuario"
PASSWORD = "somnoai2026"

EEG_CHANNEL = "EEG Fpz-Cz"          # el que se muestra en el visor y alimenta los paneles
# El modelo empaquetado usa los dos canales de EEG. Se validan al abrir el
# archivo, no cuando predice: si falta uno, el análisis completo (minutos de
# espectros) se habría tirado para nada.
EEG_CHANNELS_MODELO = ("EEG Fpz-Cz", "EEG Pz-Oz")
EPOCH_S = 30
MARGIN_EPOCHS = 60            # 30 min de margen alrededor del sueño (criterio Entrega 1)
SPECTRUM_WINDOWS = 30         # épocas NREM muestreadas para el espectro del panel
FREQ_GRID_START, FREQ_GRID_STOP, FREQ_GRID_STEP = 0.5, 25.0, 0.2
SPINDLE_BAND = (12.0, 16.0)

THRESHOLD_YEARS = 10          # umbral de priorización |BAI|
MAX_UPLOAD_MB = 600

# Noches demo (metadatos reales del índice SC-subjects de PhysioNet)
DEMOS = {
    "SC4001E0": {"psg": "SC4001E0-PSG.edf", "hyp": "SC4001EC-Hypnogram.edf",
                 "subject": "SC00", "sex": "F", "age": 33},
    "SC4701E0": {"psg": "SC4701E0-PSG.edf", "hyp": "SC4701EC-Hypnogram.edf",
                 "subject": "SC70", "sex": "M", "age": 89},
    "SC4021E0": {"psg": "SC4021E0-PSG.edf", "hyp": "SC4021EH-Hypnogram.edf",
                 "subject": "SC02", "sex": "F", "age": 26},
}

STORE_DIR.mkdir(parents=True, exist_ok=True)
MODEL_DIR.mkdir(parents=True, exist_ok=True)
