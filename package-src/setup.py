#!/usr/bin/env python
# -*- coding: utf-8 -*-

from pathlib import Path

from setuptools import find_packages, setup

# Metadatos del paquete
NAME = 'edad-cerebral'
DESCRIPTION = "Estimacion de edad cerebral a partir del EEG de una polisomnografia."
URL = "https://github.com/andriunet/SomnoAI"
EMAIL = "juancasas1996@hotmail.com"
AUTHOR = "Juan Sebastian Casas Castillo"
REQUIRES_PYTHON = ">=3.11.0"
long_description = DESCRIPTION

about = {}
ROOT_DIR = Path(__file__).resolve().parent
REQUIREMENTS_DIR = ROOT_DIR / 'requirements'
PACKAGE_DIR = ROOT_DIR / 'edad_cerebral'
# VERSION como diccionario.
with open(PACKAGE_DIR / "VERSION") as f:
    _version = f.read().strip()
    about["__version__"] = _version


# Lista de dependencias de paquetes
def list_reqs(fname="requirements.txt"):
    with open(REQUIREMENTS_DIR / fname) as fd:
        return [l for l in fd.read().splitlines() if l and not l.startswith("#")]


setup(
    name=NAME,
    version=about["__version__"],
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type="text/markdown",
    author=AUTHOR,
    author_email=EMAIL,
    python_requires=REQUIRES_PYTHON,
    url=URL,
    packages=find_packages(exclude=("tests",)),
    # El artefacto, la configuracion y las tablas de entrenamiento tienen que
    # viajar dentro del wheel: sin ellos el paquete instalado no predice ni
    # se puede reentrenar.
    package_data={"edad_cerebral": ["VERSION", "config.yml", "trained/*.pkl",
                                    "datasets/*.csv", "datasets/*.json"]},
    install_requires=list_reqs(),
    extras_require={},
    include_package_data=True,
    license="Academic use only - MAIA Uniandes",
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: Implementation :: CPython",
    ],
)
