# Contrato de API — MAIA / SomnoAI

Este documento define **lo que el tablero (frontend) espera de la API**. El equipo de
modelo/backend debe implementar estos endpoints; el frontend ya los consume tal cual
(ver `frontend/js/api.js`). Mientras la API no exista, el tablero corre en modo demo
(`frontend/js/mock.js` implementa este mismo contrato en el navegador).

- **Base sugerida:** `http://localhost:8000/api/v1` (se configura en `frontend/js/config.js`)
- **Formato:** JSON, UTF-8. Números con punto decimal (el front se encarga del formato es-CO).
- **CORS:** habilitar el origen del tablero (p. ej. `http://localhost:8080`).
- **Errores:** siempre `{"error": {"code": "...", "message": "..."}}` con el código HTTP
  correspondiente. El `message` se muestra al usuario tal cual → escribirlo en español.
- **Auth:** todos los endpoints excepto login exigen `Authorization: Bearer <token>`.
  Respuesta `401` → el front cierra la sesión y vuelve al login.

---

## 1 · Autenticación

### POST `/auth/login`

Único usuario administrador (no hay registro de cuentas).

**Request**
```json
{ "username": "superusuario", "password": "..." }
```

**Response 200**
```json
{ "token": "…", "user": { "name": "Superusuario", "initials": "SU" } }
```

**Errores:** `401 invalid_credentials`.

---

## 2 · Registros

### GET `/records`

Listado de todos los análisis guardados, **más reciente primero** (el front reordena
igualmente por `analyzed_at`).

**Response 200**
```json
{
  "records": [
    {
      "id": "a3f8…",
      "subject_code": "SC00",
      "file_name": "SC4001E0-PSG.edf",
      "analyzed_at": "2026-08-20T14:32:00",
      "sex": "F",
      "chronological_age": 33,
      "brain_age": 41.6,
      "bai": 8.6,
      "over_threshold": false,
      "model_version": "gbm-v0.4",
      "staging_source": "annotated"
    }
  ]
}
```

Notas:
- `subject_code` identifica al **sujeto**, no al archivo: `"SC" + número de sujeto`
  (convención Sleep-EDFx `SC4ssN…`: `ss` = sujeto, `N` = noche). Las dos noches de un
  mismo sujeto comparten `subject_code` — el tablero cuenta "sujetos distintos" con él.
- `sex`: `"F" | "M" | null` (para archivos nuevos puede no conocerse).
- `bai` = `brain_age − chronological_age`, redondeado a 1 decimal, **ya calibrado**
  (la corrección de regresión a la media es del modelo, no del tablero).
- `staging_source`: `"annotated"` (hipnograma del archivo) o `"auto"` (estadificación
  automática, p. ej. YASA).
- Con estos campos el front calcula los KPI (conteo, sujetos distintos, mediana, umbral).

### GET `/records/{id}`

Detalle completo de un análisis: **todo lo que pinta la vista de resultados**.

**Response 200** — el resumen anterior **más**:

```json
{
  "…resumen…": "…",
  "threshold_years": 10,

  "interval": { "level": 0.90, "typical_error": 6.1, "low": 35.5, "high": 47.7 },

  "spectrum": {
    "freqs":          [0.5, 0.7, "…", 25.0],
    "subject":        [123.4, "…"],
    "norm":           [130.1, "…"],
    "norm_band_low":  [83.2, "…"],
    "norm_band_high": [201.6, "…"],
    "spindle_band": [12, 16],
    "spindle_deficit_pct": 62,
    "spindle_age_corr_r": -0.50,
    "marker_freq": 13.2
  },

  "night": {
    "start_clock_s": 83520,
    "window_s": 30960,
    "epoch_s": 30,
    "stages": [0, 0, 1, 2, 2, 3, "…"]
  },

  "quality": {
    "composition": [
      { "label": "Vigilia previa",              "hours": 6.4, "kind": "wake" },
      { "label": "Ventana de sueño analizada",  "hours": 8.6, "kind": "sleep" },
      { "label": "Sin clasificar",              "hours": 0.6, "kind": "unscored" },
      { "label": "Vigilia posterior",           "hours": 6.4, "kind": "wake" }
    ],
    "file": {
      "name": "SC4001E0-PSG.edf",
      "size_mb": 52.3,
      "total_duration_s": 79440,
      "sampling_hz": 100,
      "channels": 7,
      "channel_used": "EEG Fpz-Cz",
      "subject_night": "Sujeto 00 · noche 1"
    },
    "analysis": {
      "sleep_window_s": 30960,
      "epochs_in_window": 1032,
      "nrem_epochs_used": 612,
      "spectrum_windows": 30,
      "epochs_discarded": 420,
      "unscored_pct": 3.1,
      "wake_trimmed_s": 46080
    }
  }
}
```

Notas por panel:
- **Hero / escala BAI:** usa `brain_age`, `chronological_age`, `bai`, `interval`,
  `threshold_years`. El intervalo es de **predicción** (cuantiles o conformal), no de
  confianza de la media.
- **Espectro:** los cinco arreglos van **alineados por índice** con `freqs`
  (misma longitud; ~120 puntos entre 0,5 y 25 Hz es suficiente). Potencias en µV²/Hz;
  el eje del front es logarítmico entre 0,1 y 1000. `norm` y su banda salen de los
  sujetos de edad similar del conjunto de entrenamiento. `spindle_deficit_pct`:
  positivo = menos husos que la norma; negativo = más. `marker_freq`: frecuencia donde
  se dibuja el marcador de divergencia.
- **Señal/visor:** `night.stages` es el hipnograma completo de la ventana de sueño,
  una entrada por época de `epoch_s` segundos, con la codificación
  `0=W, 1=N1, 2=N2, 3=N3, 4=REM`. `start_clock_s` es la hora de reloj del inicio de la
  ventana, en segundos desde las 00:00 (puede superar 86400 si cruza medianoche).
- **Calidad:** `composition[].kind` ∈ `wake | sleep | unscored` (define el color).

**Errores:** `404 not_found`.

### DELETE `/records/{id}`

Elimina el análisis (el tablero lo pide tras confirmación en un modal).
La señal derivada en disco solo se borra si ningún otro registro la comparte
(los clones de demos reutilizan la señal del original).

**Response 200:** `{"deleted": "<id>"}` · **Errores:** `404 not_found`.

---

## 3 · Análisis

### POST `/predict`

`multipart/form-data`:

| campo | tipo | reglas |
|---|---|---|
| `file` | archivo | **`.zip` con el par PSG + hipnograma**, máx. **600 MB**. Un `.edf` suelto se rechaza con `422 invalid_file`: el modelo se entrenó con hipnogramas anotados y sus características de arquitectura del sueño dependen de ellos. El registro debe traer **los dos canales de EEG** (`EEG Fpz-Cz` y `EEG Pz-Oz`); si falta uno, `422 invalid_file`. |
| `chronological_age` | entero, **opcional** | 1–120. **No entra al modelo**: solo para el BAI. Si no viene, la API la **detecta del encabezado EDF** (campo de paciente, formato Sleep-EDFx «X F X Female_33yr» — también dentro del .zip). La manual manda sobre la detectada. Si tampoco está en el encabezado → `422 age_required`. |

El resumen de cada registro incluye `age_source`: `"manual" | "edf-header" | "dataset-index"`
(el tablero muestra el origen bajo la edad cronológica). El sexo también se toma del
encabezado cuando está disponible.

Flujo esperado del backend: validar formato/canales → recortar vigilia → hipnograma
(el del archivo si viene; si no, estadificación automática y `staging_source: "auto"`) →
features NREM → inferencia → calibración del BAI → persistir → responder.

**Response 200:** el **detalle completo** (misma forma que `GET /records/{id}`).
Puede tardar minutos: el front espera hasta 10 min (síncrono está bien para el prototipo).

**Errores:** `413` (tamaño), `422 invalid_file` (formato/canales, con `message`
explicando qué faltó), `422 invalid_age`, `422 age_required` (sin edad manual ni
edad en el encabezado).

### POST `/predict-demo`

Analiza una de las noches del dataset precargadas en el servidor (idealmente
precomputadas para que la demo responda rápido).

**Request**
```json
{ "demo_id": "SC4001E0" }
```
`demo_id` ∈ `SC4001E0 | SC4701E0 | SC4021E0` — noches reales del dataset
(sujeto 00 mujer 33 años · sujeto 70 hombre 89 años · sujeto 02 mujer 26 años,
según el índice SC-subjects de PhysioNet).

**Response 200:** el detalle completo. **Errores:** `404`.

---

## 4 · Señal EEG por ventana

### GET `/records/{id}/signal?start_s=2400&duration_s=1800&points=1014`

El visor **nunca** pide la señal cruda completa: pide la **envolvente mín-máx** ya
decimada para la ventana visible. `points` ≈ píxeles disponibles (≤ 1080).

- `start_s`, `duration_s`: segundos relativos al inicio de la ventana de sueño
  (misma referencia que `night.stages`).
- Implementación: para cada uno de los `points` sub-intervalos, devolver el mín y el
  máx de las muestras del canal en ese sub-intervalo (a 100 Hz y 2 h de ventana son
  ~720.000 muestras → 1014 pares; con eso el trazo es fiel y liviano).

**Response 200**
```json
{ "start_s": 2400, "duration_s": 1800, "points": 1014, "unit": "µV",
  "min": [-42.1, "…"], "max": [38.9, "…"] }
```

**Errores:** `404`, `422 out_of_range`.

---

## 5 · Resumen de lo que pinta cada panel

| Panel del tablero | Campos que consume |
|---|---|
| KPIs + distribución BAI (Registros) | `records[]`: `bai`, `subject_code`, `analyzed_at` |
| Tabla de historial | resumen completo de cada registro |
| Hero + escala + alerta | `brain_age`, `chronological_age`, `bai`, `interval`, `threshold_years`, `model_version` |
| Espectro vs. norma | `spectrum.*` |
| Visor de señal | `night.*` + `GET …/signal` |
| Calidad del registro | `quality.*` |

## 6 · Decisiones ya tomadas que este contrato asume

- Autenticación de un solo usuario, sin registro (login de la maqueta).
- Estadificación automática (YASA) cuando el archivo no trae hipnograma.
- El BAI llega **calibrado** desde el modelo (corrección de regresión a la media).
- Umbral de priorización: ±10 años (`threshold_years` viaja en cada detalle para
  poder cambiarlo sin tocar el front).
- Análisis síncrono (sin cola de trabajos) — suficiente para el prototipo.
