# SomnoAI — Estimación de edad cerebral a partir de EEG de sueño

Prototipo funcional que estima la **edad cerebral** de una persona a partir del
EEG de una polisomnografía nocturna y calcula el **Brain Age Index (BAI)** —
la diferencia entre la edad cerebral estimada y la edad cronológica — como
criterio automático de priorización para un especialista en sueño.

Proyecto del curso *Proyecto — Desarrollo de Soluciones* de la Maestría en
Inteligencia Artificial (MAIA), Universidad de los Andes.

**Equipo:** Isabella del Pilar Camargo Salazar · Javier Andrés Marín Gallón ·
Diego Charry Cárdenas · Juan Camilo Martínez Vélez · Juan Sebastián Casas Castillo

> ⚠ **Prototipo académico de apoyo analítico. No es un instrumento de
> diagnóstico clínico.**

---

## Qué hace

- Recibe una polisomnografía (`.edf`, o `.zip` con el par PSG + hipnograma,
  hasta 600 MB) desde un tablero web.
- **Detecta automáticamente la edad y el sexo** del sujeto desde el encabezado
  EDF (también dentro del .zip); la edad manual es opcional y prevalece si se
  ingresa.
- Analiza la señal EEG real: recorta la vigilia, estadifica el sueño, calcula
  el espectro y extrae 49 características.
- Estima la edad cerebral con un modelo supervisado y calcula el BAI, con un
  umbral de priorización de ±10 años.
- Presenta los resultados en un tablero: edad cerebral con intervalo de
  predicción, BAI sobre la escala de priorización, espectro del sujeto frente a
  la norma de su edad (déficit de husos de sueño), **visor de la señal EEG**
  navegable con el hipnograma de fondo, y panel de calidad del registro.
- Guarda cada análisis en un histórico consultable (con filtros, búsqueda y
  borrado con confirmación) servido por la API.

## Cómo funciona (pipeline)

```
.edf / .zip ──► Validación (canal EEG Fpz-Cz, formato)
            ──► Edad/sexo desde el encabezado EDF («X F X Female_33yr»)
            ──► Hipnograma: anotado (archivo *-Hypnogram.edf) o YASA automático
            ──► Bloque principal de sueño ± 30 min (descarta vigilia diurna y siestas;
                los registros Sleep Cassette duran ~22 h)
            ──► Épocas NREM ──► PSD de Welch ──► espectro 0,5–25 Hz
            ──► 49 features: potencias de banda (delta/theta/alfa/sigma/beta,
                abs y relativas, por estadio N2/N3/REM y NREM global) +
                arquitectura del sueño (%N1 %N2 %N3 %REM, eficiencia, WASO,
                TST, latencia REM) + amplitud del pico de husos
            ──► Modelo (Ridge entrenado con CV agrupada por sujeto)
            ──► edad cerebral → BAI = edad cerebral − edad cronológica
```

Reglas metodológicas del proyecto:

- **La edad cronológica nunca es feature del modelo** — solo forma el BAI.
- **La validación cruzada agrupa por sujeto** (GroupKFold): las dos noches de
  una misma persona jamás se separan entre entrenamiento y prueba.
- **Las features de entrenamiento se generan con el mismo pipeline de la API**
  (`ml/build_features.py` importa `backend/app/pipeline`), garantizando
  consistencia exacta entre entrenamiento e inferencia.

## Arquitectura

```
┌──────────────┐   HTTP/JSON    ┌─────────────────────────────┐
│   Tablero    │ ─────────────► │        API (FastAPI)        │
│ (JS estático,│  contrato en   │  pipeline MNE·YASA·Welch    │
│  sin build)  │  docs/API_...  │  SQLite · señal por ventanas│
└──────────────┘                └──────────┬──────────────────┘
                                           │ model_artifacts/model.joblib
                                           │ (intercambiable sin tocar código)
                                ┌──────────┴──────────────────┐
                                │  ml/ · experimentos MLflow  │
                                │  build_features → train     │
                                └─────────────────────────────┘
```

- El visor de señal nunca recibe el EEG crudo completo: la API sirve la
  **envolvente mín-máx** por ventana visible (`GET /records/{id}/signal`).
- El modelo es un artefacto `joblib` intercambiable: reemplazarlo y reiniciar
  la API basta para servir una nueva versión (ver `backend/README.md`).

## Estructura del repositorio

```
frontend/                 Tablero (HTML+JS puro, sin dependencias ni build)
  index.html              vistas y estilos (fiel a la maqueta de la Entrega 1)
  js/config.js            apiBase: URL de la API, o null = modo demo sin backend
  js/api.js · js/mock.js  cliente de API · backend simulado del modo demo
  js/charts.js · js/app.js  gráficos SVG · lógica de la aplicación
backend/
  app/main.py             endpoints de la API (contrato en docs/API_CONTRACT.md)
  app/pipeline/           edf_io · staging (anotado/YASA) · analysis · norms
  app/model/predictor.py  carga del modelo empaquetado
  model_artifacts/        model.joblib servido por la API (incluido: ridge-v1)
  data/demo/download_demos.sh   descarga las 3 noches demo de PhysioNet (~148 MB)
  requirements.txt        dependencias completas con versiones fijadas
  Dockerfile · run.sh
ml/
  build_features.py       EDFs → tabla de features (usa el pipeline de la API)
  train.py                Ridge/RF/GBoosting + GroupKFold + registro en MLflow
  age_records.csv         índice oficial de las 153 noches (sujeto, edad, sexo)
docs/
  API_CONTRACT.md         contrato completo front ↔ API (JSON de cada endpoint)
  MLFLOW_EC2.md           runbook para llevar MLflow a AWS EC2 + checklist de soportes
  REPORTE_BORRADOR.md     esqueleto del reporte de la Entrega 2
docker-compose.yml        despliegue: API (build) + tablero (nginx estático)
```

## Requisitos

- **Python 3.12** (probado con 3.12.7) y `pip`.
- macOS o Linux (Windows vía WSL debería funcionar; no probado).
- ~200 MB de disco para las noches demo (o ~8 GB para el dataset completo).
- Docker Desktop solo si se usa el despliegue con contenedores.

## Instalación y ejecución

```bash
git clone https://github.com/andriunet/SomnoAI.git && cd SomnoAI

# 1 · entorno del backend
python3 -m venv --system-site-packages backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
#   (si la red tiene proxy TLS: añadir --trusted-host pypi.org --trusted-host files.pythonhosted.org)

# 2 · datos demo (3 noches reales de Sleep-EDFx, ~148 MB)
sh backend/data/demo/download_demos.sh

# 3 · API — primer arranque precomputa los demos (~30 s) → http://localhost:8000
cd backend && ./run.sh

# 4 · tablero (otra terminal) → http://localhost:8080
cd frontend && python3 -m http.server 8080
```

Credenciales del prototipo: **superusuario / somnoai2026**.
Estado del servicio: `GET http://localhost:8000/api/v1/health` · documentación
interactiva de la API en `http://localhost:8000/docs`.

### Con Docker

```bash
sh backend/data/demo/download_demos.sh   # los datos van por volumen, no en la imagen
docker compose up --build                # tablero :8080 · API :8000
```

### Modo demo (solo frontend, sin backend)

`frontend/js/config.js` → `apiBase: null`. El tablero corre con un backend
simulado en el navegador (datos sintéticos en localStorage) — útil para
trabajar la interfaz sin Python.

## Probar la API con curl

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"superusuario","password":"somnoai2026"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# listado del histórico
curl -s http://localhost:8000/api/v1/records -H "Authorization: Bearer $TOKEN"

# analizar un archivo (la edad se detecta del encabezado; -F chronological_age=NN para fijarla)
curl -s -X POST http://localhost:8000/api/v1/records/analyze \
  -H "Authorization: Bearer $TOKEN" -F "file=@mi_registro.zip"

# borrar un registro
curl -s -X DELETE http://localhost:8000/api/v1/records/<id> -H "Authorization: Bearer $TOKEN"
```

El contrato completo (todos los campos JSON) está en `docs/API_CONTRACT.md`.

## Experimentos (MLflow)

```bash
# tracking server local → http://127.0.0.1:5500 (los runs, en la pestaña "Model training")
backend/.venv/bin/mlflow server --host 127.0.0.1 --port 5500 \
  --backend-store-uri sqlite:///ml/mlserver/mlflow.db \
  --artifacts-destination ./ml/mlserver/artifacts

# features (usa el pipeline de la API) y entrenamiento con CV por sujeto
backend/.venv/bin/python ml/build_features.py --data-dir backend/data/demo
MLFLOW_TRACKING_URI=http://127.0.0.1:5500 backend/.venv/bin/python ml/train.py
```

`train.py` compara Ridge, Random Forest y Gradient Boosting, registra MAE/RMSE/R²
out-of-fold y `corr(BAI, edad)` (el indicador del sesgo de regresión a la media),
y guarda el mejor modelo en `ml/out/model.joblib` con el formato que la API
consume. Para servirlo: `cp ml/out/model.joblib backend/model_artifacts/` y
reiniciar la API. El runbook para llevar el tracking a AWS EC2 (requisito de la
entrega) está en `docs/MLFLOW_EC2.md`.

El modelo incluido en el repo (`ridge-v1`) fue entrenado con un subconjunto
estratificado de 29 sujetos (25–101 años): MAE 15,6 años en CV por sujeto.
Con las 153 noches completas la referencia a superar es MAE 10,2 (línea base
Ridge de la Entrega 1).

## Fuentes de datos y referencias

**Datos:** [Sleep-EDF Database Expanded v1.0.0](https://physionet.org/content/sleep-edfx/1.0.0/)
(PhysioNet), subconjunto **Sleep Cassette**: 153 noches de 78 sujetos sanos
(25–101 años), EEG Fpz-Cz a 100 Hz + hipnogramas anotados por expertos.
Los archivos no se versionan en este repo: se descargan con
`backend/data/demo/download_demos.sh` (demos) o desde PhysioNet/DVC (dataset
completo). `ml/age_records.csv` es el índice de sujetos (edad/sexo/archivos).

- Kemp B. et al. *Analysis of a sleep-dependent neuronal feedback loop: the
  slow-wave microcontinuity of the EEG.* IEEE Trans Biomed Eng, 2000.
- Goldberger A.L. et al. *PhysioBank, PhysioToolkit, and PhysioNet.*
  Circulation, 2000.
- Sun H. et al. *Brain age from the electroencephalogram of sleep.*
  Neurobiology of Aging, 2019 — metodología de referencia para brain age con
  features por estadio.
- Paixao L. et al. *Excess brain age in the sleep electroencephalogram predicts
  reduced life expectancy.* Neurobiology of Aging, 2020.
- Vallat R., Walker M.P. *An open-source, high-performance tool for automated
  sleep staging (YASA).* eLife, 2021 — estadificación automática usada aquí.
- Gramfort A. et al. *MEG and EEG data analysis with MNE-Python.* Frontiers in
  Neuroscience, 2013 — lectura y manejo de EDF.

Nota de calidad de datos: existen discrepancias puntuales entre el índice
SC-subjects y los encabezados EDF (p. ej. SC4231: índice 50/F, encabezado
«Male_49yr»); la inferencia usa el encabezado.

## Estado y hoja de ruta

Ver `docs/REPORTE_BORRADOR.md` y la página de estado del equipo. Pendientes
principales: reentrenar con las 153 noches (+ calibración del BAI e intervalo
de predicción), experimentos en MLflow sobre EC2 con sus soportes, y el reporte
final.

## Licencia y uso

Proyecto académico (MAIA · Universidad de los Andes, 2026). Los datos de
Sleep-EDFx son de PhysioNet y conservan su licencia original (ODC-BY 1.0).
Este software se comparte con fines educativos; **no debe usarse para tomar
decisiones clínicas**.
