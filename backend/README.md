# MAIA / SomnoAI — Backend (API + pipeline)

API de FastAPI que implementa `../docs/API_CONTRACT.md` con el **pipeline real**:
lee polisomnografías EDF de Sleep-EDFx, recorta la vigilia, estadifica
(hipnograma anotado o YASA), extrae características espectrales y de
arquitectura del sueño, y sirve todo lo que pinta el tablero — incluida la
señal EEG por ventanas.

## Cómo correrlo

```bash
cd backend
./run.sh          # → http://localhost:8000 (docs interactivas en /docs)
```

Con Docker (desde la raíz del proyecto): `docker compose up --build` — ver
`../docker-compose.yml`. La imagen no incluye datos ni modelo: `data/` y
`model_artifacts/` se montan como volúmenes.

Primer arranque: precomputa los 3 demos con los EDF reales de `data/demo/`
(descargados de PhysioNet). El tablero (frontend/) apunta aquí vía
`frontend/js/config.js` → `apiBase`.

Si el venv no existe: `python3 -m venv --system-site-packages .venv &&
./.venv/bin/pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt`
(los `--trusted-host` son por el proxy corporativo).

## ⚠ QUÉ ES REAL Y QUÉ ES PROVISIONAL

**Real** (pipeline completo sobre la señal):
- Lectura EDF/zip, validación de canal (`EEG Fpz-Cz`), recorte de vigilia con
  detección del bloque principal de sueño (ignora siestas y micro-episodios).
- Hipnograma anotado (`*-Hypnogram.edf`) o **YASA** para archivos sin hipnograma.
- Espectro NREM (Welch), features espectrales por estadio y de arquitectura.
- Métricas de calidad, señal EEG servida por ventanas (envolvente mín-máx).

**Provisional** (lo reemplaza el equipo de modelado):
1. **El modelo de edad** — hoy es un heurístico (`heuristic-v0`) anclado en las
   correlaciones de la Entrega 1. El tablero lo muestra como "(provisional)".
2. **La norma espectral por edad** (`app/pipeline/norms.py`) — el 1/f se ajusta
   al sujeto y la amplitud de husos esperada usa una recta; debe salir de
   percentiles empíricos del conjunto de entrenamiento.
3. **typical_error ±10,2** — es el MAE del Ridge de la Entrega 1; el real sale
   de la validación cruzada del modelo final (idealmente cuantílico/conformal).

## Cómo enchufar el modelo real (equipo de modelado)

Guardar `backend/model_artifacts/model.joblib` con:

```python
import joblib
joblib.dump({
    "model": modelo_entrenado,            # .predict(DataFrame) → años
    "feature_names": [...],               # columnas esperadas, en orden
    "meta": {
        "version": "gbm-v1.0",            # aparece en la píldora del tablero
        "typical_error": 8.3,             # semiancho del intervalo (años)
        "interval_level": 0.90,
    },
}, "backend/model_artifacts/model.joblib")
```

y reiniciar la API. Nada más. Las **features disponibles** (nombres exactos)
las produce `app/pipeline/analysis.py` y viajan en `detail["features"]` de
cada análisis (véanse en `/docs` o en una respuesta real):
`nrem_{delta,theta,alpha,sigma,beta}_{abs,rel}`, `n2_*`, `n3_*`, `rem_*`,
`pct_n1`, `pct_n2`, `pct_n3`, `pct_rem`, `sleep_efficiency`, `waso_min`,
`tst_min`, `rem_latency_min`, `spindle_amp`.

**Regla del proyecto:** la edad cronológica NO es feature, y la corrección de
regresión a la media del BAI debe venir calibrada dentro del modelo.

IMPORTANTE para entrenar consistente con producción: generen su tabla de
features con ESTE pipeline (`analysis.run_analysis`) sobre las 153 noches,
así lo que ve el modelo en entrenamiento es idéntico a lo que ve al inferir.

## Estructura

```
app/main.py                endpoints (contrato en ../docs/API_CONTRACT.md)
app/pipeline/edf_io.py     carga y validación EDF/zip
app/pipeline/staging.py    hipnograma anotado | YASA
app/pipeline/analysis.py   recorte, PSD, features, calidad → detalle completo
app/pipeline/norms.py      norma espectral por edad (PROVISIONAL)
app/model/predictor.py     punto de enchufe del modelo (model_artifacts/)
app/signals.py             señal int16 0,1 µV + envolvente por ventana
app/db.py                  SQLite en data/store/maia.db
data/demo/                 3 noches reales de Sleep-EDFx (PhysioNet)
data/store/                BD y señales derivadas (se regenera al borrar)
```
