"""Configuración validada del paquete.

Mismo patrón que el Taller 5: un config.yml, unos modelos de Pydantic que lo
validan, y un objeto `config` de módulo que importa el resto del paquete.

Dos diferencias respecto del taller, ambas deliberadas:

- Se usa PyYAML en vez de strictyaml. strictyaml sin esquema parsea todo como
  cadenas; aquí hay diccionarios anidados (bandas, etapas) y listas de pares
  (canales), y forzar esa coerción a mano sería más frágil que validarla con
  Pydantic directamente.
- El campo se llama `modelo`, no `model_config`: Pydantic v2 reserva ese nombre
  para su propia configuración de clase y usarlo como campo revienta.
"""
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import yaml
from pydantic import BaseModel

import edad_cerebral

PACKAGE_ROOT = Path(edad_cerebral.__file__).resolve().parent
ROOT = PACKAGE_ROOT.parent
CONFIG_FILE_PATH = PACKAGE_ROOT / "config.yml"
DATASET_DIR = PACKAGE_ROOT / "datasets"
TRAINED_MODEL_DIR = PACKAGE_ROOT / "trained"


class AppConfig(BaseModel):
    """Identidad del paquete y nombre del artefacto."""

    paquete: str
    version_modelo: str
    archivo_modelo: str
    csv_fpz: str
    csv_pz: str
    particion: str


class ModeloConfig(BaseModel):
    """Todo lo que define cómo se extraen las características y cómo predice."""

    # extracción (notebook 02)
    epoca_s: int
    rango_hz: Tuple[float, float]
    nperseg_epocas: int
    escala_psd: float
    bandas: Dict[str, Tuple[float, float]]
    canales: List[Tuple[str, str]]
    amplitud_uv_esperada: Tuple[float, float]
    etapas: Dict[str, str]
    etapas_dormido: Sequence[str]

    # modelo (notebook 03, experimento C)
    alpha: float
    lam: float
    mae_validacion: float
    nivel_intervalo: float
    metricas_esperadas: Dict[str, float]
    espectrales: List[str]
    arquitectura: List[str]

    @property
    def columnas(self) -> List[str]:
        """Las 32 columnas en el orden exacto que espera el pipeline.

        El orden es parte del contrato: el pipeline recibe un array, no un
        DataFrame con nombres. Se construye igual que en el notebook 03.
        """
        cols: List[str] = []
        for _, sufijo in self.canales:
            cols += [f"mix_{e}_{sufijo}" for e in self.espectrales]
        return cols + list(self.arquitectura)


class Config(BaseModel):
    """Configuración completa."""

    app_config: AppConfig
    modelo: ModeloConfig


def find_config_file() -> Path:
    if CONFIG_FILE_PATH.is_file():
        return CONFIG_FILE_PATH
    raise FileNotFoundError(f"No se encontró la configuración en {CONFIG_FILE_PATH!r}")


def fetch_config_from_yaml(cfg_path: Path | None = None) -> dict:
    with open(cfg_path or find_config_file(), encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_and_validate_config(parsed: dict | None = None) -> Config:
    parsed = parsed if parsed is not None else fetch_config_from_yaml()
    return Config(app_config=AppConfig(**parsed), modelo=ModeloConfig(**parsed))


config = create_and_validate_config()
