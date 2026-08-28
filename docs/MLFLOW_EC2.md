# Runbook · MLflow en AWS EC2 (soportes de la Entrega 2)

Lo que el PDF exige: *"Pantallazos de experimentos registrados en MLflow en una
máquina de AWS EC2 (debe ser visible el usuario e IP de la máquina en EC2, y la
IP en MLflow). Mantenga su máquina en EC2 con MLflow detenida (no la termine)."*

## Qué ya funciona (probado en local)

- `ml/build_features.py` — tabla de features con **el mismo pipeline de la API**
  (garantiza consistencia entrenamiento ↔ inferencia). Probado con las 3 noches
  reales de `backend/data/demo/`.
- `ml/train.py` — Ridge vs. Random Forest vs. Gradient Boosting con
  **GroupKFold por sujeto**, métricas OOF (MAE, RMSE, R², corr(BAI, edad) que
  delata la regresión a la media), scatter OOF como artefacto, y el bundle del
  mejor modelo en el formato exacto que consume la API.
- Tracking server local verificado en `http://127.0.0.1:5500` (4 runs).

Probar en local (todo desde la raíz del proyecto):

```bash
# 1 · tracking server local
backend/.venv/bin/mlflow server --host 127.0.0.1 --port 5500 \
    --backend-store-uri sqlite:///ml/mlserver/mlflow.db \
    --artifacts-destination ./ml/mlserver/artifacts

# 2 · features + experimentos (otra terminal)
backend/.venv/bin/python ml/build_features.py --data-dir backend/data/demo
MLFLOW_TRACKING_URI=http://127.0.0.1:5500 backend/.venv/bin/python ml/train.py
```

⚠ **MLflow 3.x**: la UI abre en modo "GenAI"; los runs están en la pestaña
**"Model training"** (arriba a la izquierda). Ese es el pantallazo que vale.

## Qué falta (en orden)

### 1 · Las 153 noches (hoy solo hay 3)

Con 3 sujetos las métricas no significan nada (MAE ~39, corr(BAI,edad) = −1: la
demostración perfecta del sesgo de regresión a la media, útil para el reporte).
Opciones para el dataset completo (~8 GB):

```bash
# opción A: el DVC del equipo (repo MAIA_Proyecto_Desarrollo_De_Soluciones)
dvc pull

# opción B: PhysioNet directo (subconjunto sleep-cassette)
wget -r -N -np -nd -A "SC4*" -P data/sleep-cassette \
  https://physionet.org/files/sleep-edfx/1.0.0/sleep-cassette/
```

Luego: `build_features.py --data-dir <carpeta>` (~3–5 min las 153 noches) y
`train.py`. Ahí las métricas ya son reales (referencia a superar: Ridge de la
Entrega 1, MAE 10,2).

### 2 · EC2 en AWS Academy (una sola sesión del Learner Lab)

1. **Iniciar el Learner Lab** y entrar a la consola AWS → EC2 → *Launch instance*:
   - Amazon Linux 2023 · `t3.small` (suficiente: solo trackea) · key pair `vockey`.
   - Security group: SSH (22) y **Custom TCP 5000**, ambos con origen
     *My IP* (evitar 0.0.0.0/0).
2. **Instalar y arrancar MLflow** en la instancia:
   ```bash
   ssh -i labsuser.pem ec2-user@<IP_PUBLICA>
   sudo dnf install -y python3-pip
   python3 -m pip install --user mlflow
   nohup ~/.local/bin/mlflow server --host 0.0.0.0 --port 5000 \
       --backend-store-uri sqlite:///mlflow.db \
       --artifacts-destination ./mlartifacts > mlflow.log 2>&1 &
   ```
3. **Correr los experimentos desde el portátil** (el cómputo es local, solo el
   registro viaja a EC2):
   ```bash
   MLFLOW_TRACKING_URI=http://<IP_PUBLICA>:5000 backend/.venv/bin/python ml/train.py
   ```
4. **Pantallazos** (todos en esta misma sesión — la IP cambia si el lab se reinicia):
   - [ ] Consola EC2, detalle de la instancia: **usuario del lab visible arriba a la
         derecha** + **IP pública visible**.
   - [ ] Navegador en `http://<IP_PUBLICA>:5000` → pestaña **Model training** →
         tabla de runs, **con la IP visible en la barra de direcciones**.
   - [ ] Detalle de un run: parámetros (GroupKFold por sujeto, n_nights=153) y
         métricas (mae_oof, bai_age_corr).
   - [ ] Un artefacto abierto (oof_scatter.png o el model.joblib del run final).
5. **Detener la instancia (Stop, NO Terminate)** — requisito literal del PDF.

### 3 · Promover el modelo ganador a la API

```bash
cp ml/out/model.joblib backend/model_artifacts/model.joblib
# reiniciar la API → el tablero deja de decir "provisional"
curl http://localhost:8000/api/v1/health   # confirma la versión del modelo
```

Antes de promoverlo, ajustar en `ml/train.py` lo que el equipo decida sobre la
**calibración del BAI** (regresión a la media) y el **intervalo de predicción**
(cuantílico/conformal) — hoy `typical_error` usa el MAE de CV como aproximación.

## Notas de AWS Academy

- La sesión del lab expira (~4 h) y **la IP pública cambia** entre sesiones →
  experimentos y pantallazos en una sola sentada.
- La cuenta no permite IAM/accesos externos: los soportes son los pantallazos.
- Si el proxy corporativo rompe `pip` en EC2 no aplica (la instancia sale a
  internet directo); si rompe la conexión del portátil a `:5000`, probar desde
  otra red o hotspot.
