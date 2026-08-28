# Microproyecto — Entrega 2 · BORRADOR DE TRABAJO

> **SomnoAI: Estimación automática de la edad cerebral a partir de polisomnografía**
> Equipo: Isabella del Pilar Camargo Salazar · Javier Andrés Marín Gallón ·
> Diego Charry Cárdenas · Juan Camilo Martínez Vélez · Juan Sebastián Casas Castillo
>
> ⚠ Borrador para repartir entre el equipo. Máximo **10 páginas** en el documento
> final — este esqueleto está dimensionado para eso. Los bloques `[PENDIENTE]`
> requieren los resultados con las 153 noches y/o decisiones del equipo.
> Regla del PDF: *"cada gráfica y afirmación importa"* — priorizar.

---

## 1 · Resumen del problema (máx. 1 página)

**Contexto.** (Comprimir de la Entrega 1 en ~1 párrafo: EEG de sueño cambia
sistemáticamente con la edad; BAI = edad cerebral estimada − edad cronológica
como índice de priorización; apoyo analítico, no diagnóstico.)

**Pregunta de negocio.** (Copiar de la Entrega 1, 2–3 líneas.)

**Datos.** Sleep-EDFx · Sleep Cassette: 153 noches, 78 sujetos, 25–101 años.
EEG Fpz-Cz a 100 Hz + hipnograma anotado.

**Cambios respecto a la Entrega 1** (el PDF pide resaltarlos):
- La estadificación para registros nuevos sin hipnograma se resolvió con **YASA**
  (estadificador automático publicado, LightGBM); se descartó integrar
  TinySleepNet/DeepSleepNet por costo de integración sin ganancia de exactitud
  (~85 % en ambos sobre Sleep-EDF). [cita YASA: Vallat & Walker 2021]
- La ventana de análisis pasó de "sueño ± 30 min" a **bloque principal de
  sueño** (los registros cubren 22 h e incluyen siestas diurnas que
  distorsionaban la ventana — hallazgo al procesar sujetos mayores).
- El frontend se implementó adaptando directamente la maqueta (JS sin
  dependencias) en lugar de React: menor riesgo en el cronograma y fidelidad
  total a la maqueta calificada en la Entrega 1.
- `[PENDIENTE: otros cambios que el equipo decida resaltar]`

## 2 · Solución construida (≈ 1,5 páginas)

**Arquitectura.** Tablero (estático) → API FastAPI → pipeline de señal
(MNE + YASA + Welch) → modelo empaquetado (joblib) → SQLite. Despliegue con
Docker Compose (2 contenedores + volúmenes para datos y modelo). MLflow como
tracking de experimentos en EC2.
`[FIGURA 1: diagrama de arquitectura — media página máx.]`

**Pipeline de inferencia** (idéntico en entrenamiento e inferencia — punto
metodológico clave): validación del EDF y canal Fpz-Cz → hipnograma anotado o
YASA → detección del bloque principal de sueño → épocas NREM → PSD de Welch
por estadio → 49 features espectrales (bandas abs/rel por estadio) y de
arquitectura (%N1, %N3, eficiencia, WASO, latencia REM…) → modelo → BAI.

## 3 · Modelos desarrollados y su evaluación (≈ 2,5 páginas)

**Protocolo.** Validación cruzada agrupada por sujeto (GroupKFold): las dos
noches de una persona jamás se separan entre entrenamiento y prueba. La edad
cronológica NO es feature. Métricas out-of-fold: MAE, RMSE, R², y
**corr(BAI, edad)** como indicador del sesgo de regresión a la media.

**Modelos comparados.** Ridge (línea base de la Entrega 1) · Random Forest ·
Gradient Boosting. `[PENDIENTE: hiperparámetros finales y variantes probadas]`

`[TABLA 1: resultados por modelo con las 153 noches — sale directa de MLflow]`
| Modelo | MAE (años) | RMSE | R² | corr(BAI, edad) |
|---|---|---|---|---|
| Naive (edad media) | 18,3* | — | — | — |
| Ridge | `[PEND]` | | | |
| Random Forest | `[PEND]` | | | |
| Gradient Boosting | `[PEND]` | | | |

*\*valor de la Entrega 1; recalcular con la partición final.*

`[FIGURA 2: dispersión edad real vs. estimada (OOF) del mejor modelo — artefacto de MLflow]`

**Calibración del BAI.** `[PENDIENTE — decisión del equipo: método de corrección
de la regresión a la media (p. ej. residuo sobre regresión de predicción~edad
ajustada en los folds de entrenamiento) y su efecto sobre corr(BAI, edad).]`

**Intervalo de predicción.** `[PENDIENTE — decisión del equipo: cuantílico o
conformal split al 90 %; hoy la API aproxima con el MAE de CV.]`

**Experimentos en MLflow (EC2).** Todos los experimentos quedaron versionados
en un tracking server en AWS EC2. `[FIGURA 3: pantallazo de la tabla de runs
con la IP visible — checklist completo en docs/MLFLOW_EC2.md]`

## 4 · Observaciones y conclusiones sobre los modelos (≈ 1,5 páginas)

Semillas (validadas ya con el subconjunto local; confirmar con 153):
- Los marcadores dominantes de edad no son la cantidad de sueño sino su
  composición: husos de sueño (banda sigma) y %N3 — coherente con la Entrega 1
  (r = −0,50 y −0,42) y con Sun et al. 2019.
- Caso ilustrativo real: el sujeto 70 (89 años) duerme *consolidado*
  (eficiencia 0,98 en su bloque principal) pero con husos ≈ 0 y N3 = 3,8 % —
  la edad está en la microestructura, no en la duración.
- Sin calibración, el BAI correlaciona negativo con la edad (regresión a la
  media): el índice marcaría jóvenes como "envejecidos". `[PENDIENTE: valor
  final tras calibración]`
- **Sensibilidad a la fuente de estadificación** (hallazgo empírico): un mismo
  registro (sujeto 02) produce edad cerebral 45,1 con hipnograma anotado pero
  79,3 con estadificación YASA — el modelo entrenado sobre hipnogramas anotados
  extrapola mal cuando las features vienen de estadificación automática.
  Mitigación a evaluar en MLflow: entrenar también con features derivadas de
  YASA (consistencia entrenamiento-inferencia para archivos sin hipnograma).
- Cota superior del estado del arte: MAE ~4–6 años con >13.000 PSG y deep
  learning (Nature & Science of Sleep 2024); con 78 sujetos, features + GBM es
  la elección metodológicamente correcta. [citas]
- **Calidad de metadatos del dataset**: hay discrepancias entre SC-subjects.xls
  y los encabezados EDF (p. ej. SC4231: índice 50/F vs. encabezado «Male_49yr»).
  El pipeline usa el encabezado en inferencia; conciliar antes del entrenamiento
  definitivo con las 153 noches.
- `[PENDIENTE: limitaciones — huecos etarios 35–49 y 75–84, exclusión SC4092,
  norma espectral provisional vs. empírica]`

## 5 · Tablero desarrollado y su funcionalidad (≈ 1,5 páginas)

Tres pantallas fieles a la maqueta de la Entrega 1 (login de usuario único ·
registros · análisis/resultados):
- **Registros**: KPIs calculados del histórico, distribución del BAI con umbral
  de priorización ±10 años, tabla con filtros y búsqueda.
- **Analizar**: carga de .edf o .zip (≤600 MB) + edad cronológica (no entra al
  modelo; solo forma el BAI). Estadificación automática si no hay hipnograma.
- **Resultados**: edad cerebral con intervalo, BAI sobre la escala de
  priorización con alertas, espectro del sujeto vs. norma de su edad (déficit
  de husos), visor de la señal EEG con hipnograma y navegación por la noche
  (la señal viaja como envolvente mín-máx por ventana — nunca cruda), y panel
  de calidad del registro (composición de las 22 h, épocas usadas/descartadas).

`[FIGURA 4: pantallazo de resultados con un registro real — sugerido: sujeto 70]`

La API implementa un contrato documentado (docs/API_CONTRACT.md) con /health
para monitoreo; el modelo se actualiza reemplazando un único artefacto joblib
sin tocar código. Despliegue: `docker compose up --build`.

## 6 · Soportes (lista de verificación del PDF)

- [ ] Repositorio con el código y commits de los 5 integrantes
- [ ] Pantallazos MLflow en EC2: usuario e IP visibles · instancia detenida
- [ ] Fuentes de modelos (`ml/`) y del tablero (`frontend/`, `backend/`)
- [ ] Reporte de trabajo en equipo (1 página — tabla integrante/aporte/ramas/PRs
      como en la Entrega 1)

## Referencias

Mantener [1]–[5] de la Entrega 1 y añadir:
- Vallat R, Walker MP. An open-source, high-performance tool for automated
  sleep staging (YASA). eLife 2021.
- `[Multi-flow sequence learning for brain age — Nature & Science of Sleep 2024]`
- `[Supratak & Guo, TinySleepNet, EMBC 2020 — citado como alternativa evaluada]`
