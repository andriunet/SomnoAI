# Runbook · MLflow en AWS EC2 (soportes de la Entrega 2)

Lo que el PDF exige: *"Pantallazos de experimentos registrados en MLflow en una
máquina de AWS EC2 (debe ser visible el usuario e IP de la máquina en EC2, y la
IP en MLflow). Mantenga su máquina en EC2 con MLflow detenida (no la termine)."*

## Qué ya funciona

- `ml/build_features.py` — tabla de features con **el mismo pipeline de la API**
  (garantiza consistencia entrenamiento ↔ inferencia). Ya corrido sobre las 153
  noches completas → `ml/out/features_full.csv` (153 noches · 78 sujetos · 49
  features Fpz-Cz).
- `ml/train.py` — Ridge vs. Random Forest vs. Gradient Boosting con
  **GroupKFold por sujeto**, métricas OOF (MAE, RMSE, R², corr(BAI, edad) que
  delata la regresión a la media), scatter OOF como artefacto, y el bundle del
  mejor modelo en el formato exacto que consume la API. Soporta `--split
  ml/subject_split_seed42.json` para correr sobre la partición fija del equipo
  (62 sujetos dev / 16 test).
- `ml/tune_ridge.py` — barrido de `alpha` para Ridge (línea base del proyecto;
  ningún otro modelo la superó en el bake-off de ocho familias que corrió
  Sebastián — ver `Experimentos/Sebastian/README.md` en el repo del equipo y el
  experimento `edad-cerebral-sebastian` en MLflow). Misma rejilla log de 13
  valores (1e-2…1e4), misma partición fija y mismo criterio de selección
  (menor MAE de CV entre los alphas que baten la media y controlan la
  regresión a la media) para que los números sean comparables con los suyos.
- **Tracking server del equipo en EC2, ya arriba**: `http://13.223.193.36:8050`
  (experimentos existentes: `edad-cerebral-sebastian`,
  `edad-cerebral-JuanCamilo-RandomForest-Features`,
  `edad-cerebral-Diego-Ridge-CV`).

Correr contra el server del equipo (desde la raíz del proyecto):

```bash
MLFLOW_TRACKING_URI=http://13.223.193.36:8050 backend/.venv/bin/python ml/tune_ridge.py
# o el bake-off completo (Ridge/RF/GB) con alpha fijo:
MLFLOW_TRACKING_URI=http://13.223.193.36:8050 backend/.venv/bin/python ml/train.py \
    --features ml/out/features_full.csv --split ml/subject_split_seed42.json
```

Probar contra un server local en vez del de EC2 (todo desde la raíz del proyecto):

```bash
# 1 · tracking server local
backend/.venv/bin/mlflow server --host 127.0.0.1 --port 5500 \
    --backend-store-uri sqlite:///ml/mlserver/mlflow.db \
    --artifacts-destination ./ml/mlserver/artifacts

# 2 · features + experimentos (otra terminal)
MLFLOW_TRACKING_URI=http://127.0.0.1:5500 backend/.venv/bin/python ml/tune_ridge.py
```

⚠ **MLflow 3.x**: la UI abre en modo "GenAI"; los runs están en la pestaña
**"Model training"** (arriba a la izquierda). Ese es el pantallazo que vale.
También: el backend de archivos (`./mlruns` sin base de datos) está en
mantenimiento y MLflow 3.x lo rechaza — usar siempre `sqlite:///...` o un
tracking server real.

## Qué falta (en orden)

### 1 · EC2 en AWS Academy (si hay que reiniciar el server del equipo)

El server compartido ya está arriba en `13.223.193.36:8050` (nótese: puerto
**8050**, no el 5000 por defecto de MLflow — así quedó configurada la
instancia del equipo). Esto es solo referencia por si hay que levantar uno
nuevo porque expiró la sesión del Learner Lab:

1. **Iniciar el Learner Lab** y entrar a la consola AWS → EC2 → *Launch instance*:
   - Amazon Linux 2023 · `t3.small` (suficiente: solo trackea) · key pair `vockey`.
   - Security group: SSH (22) y **Custom TCP** en el puerto que se vaya a usar,
     con origen *My IP* (evitar 0.0.0.0/0).
2. **Instalar y arrancar MLflow** en la instancia:
   ```bash
   ssh -i labsuser.pem ec2-user@<IP_PUBLICA>
   sudo dnf install -y python3-pip
   python3 -m pip install --user mlflow
   nohup ~/.local/bin/mlflow server --host 0.0.0.0 --port 8050 \
       --backend-store-uri sqlite:///mlflow.db \
       --artifacts-destination ./mlartifacts > mlflow.log 2>&1 &
   ```
3. **Correr los experimentos desde el portátil** (el cómputo es local, solo el
   registro viaja a EC2):
   ```bash
   MLFLOW_TRACKING_URI=http://<IP_PUBLICA>:8050 backend/.venv/bin/python ml/tune_ridge.py
   ```
4. **Pantallazos** (todos en esta misma sesión — la IP cambia si el lab se reinicia):
   - [ ] Consola EC2, detalle de la instancia: **usuario del lab visible arriba a la
         derecha** + **IP pública visible**.
   - [ ] Navegador en `http://<IP_PUBLICA>:8050` → pestaña **Model training** →
         tabla de runs, **con la IP visible en la barra de direcciones**.
   - [ ] Detalle de un run: parámetros (GroupKFold por sujeto, alpha) y métricas
         (mae_oof, bai_age_corr).
   - [ ] Un artefacto abierto (ridge_alpha_sweep.png o el model_ridge_cv.joblib
         del run final).
5. **Detener la instancia (Stop, NO Terminate)** — requisito literal del PDF.

### 2 · Promover el modelo ganador a la API

```bash
cp ml/out/model_ridge_cv.joblib backend/model_artifacts/model.joblib
# reiniciar la API → el tablero deja de decir "provisional"
curl http://localhost:8000/api/v1/health   # confirma la versión del modelo
```

Antes de promoverlo, ajustar lo que el equipo decida sobre la **calibración
del BAI** (regresión a la media — hoy `bai_age_corr` sigue negativo incluso en
el mejor alpha) y el **intervalo de predicción** (cuantílico/conformal) — hoy
`typical_error` usa el MAE de CV como aproximación.

## Notas de AWS Academy

- La sesión del lab expira (~4 h) y **la IP pública cambia** entre sesiones →
  experimentos y pantallazos en una sola sentada.
- La cuenta no permite IAM/accesos externos: los soportes son los pantallazos.
- Si el proxy corporativo rompe `pip` en EC2 no aplica (la instancia sale a
  internet directo); si rompe la conexión del portátil a `:5000`, probar desde
  otra red o hotspot.
