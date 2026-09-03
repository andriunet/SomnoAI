"""Experimentos de edad cerebral registrados en MLflow.

Compara Ridge (línea base de la Entrega 1), Random Forest y Gradient Boosting
con validación cruzada AGRUPADA POR SUJETO (regla del proyecto: las dos noches
de una persona nunca se separan entre train y test). Registra en MLflow:
parámetros, métricas OOF (MAE, RMSE, R², correlación BAI-edad), la gráfica
de dispersión y el bundle del mejor modelo en el formato que consume la API.

Uso:
    # local (URI por defecto: carpeta ml/mlruns)
    ./backend/.venv/bin/python ml/train.py

    # contra un tracking server (local o EC2)
    MLFLOW_TRACKING_URI=http://<IP>:5000 ./backend/.venv/bin/python ml/train.py

    # con la partición fija del proyecto (dev/test por sujeto, ver
    # ml/subject_split_seed42.json): la métrica defendible sigue siendo la de
    # CV sobre dev; el número de test se calcula una sola vez, al final.
    ./backend/.venv/bin/python ml/train.py --split ml/subject_split_seed42.json

La edad cronológica NO es feature. El bundle final queda en ml/out/model.joblib:
cuando esté entrenado con las 153 noches, copiarlo a backend/model_artifacts/
para que la API lo sirva.
"""
import argparse
import json
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HERE = Path(__file__).parent
META_COLS = ["fname", "subject", "night", "age", "sex"]

MODELS = {
    "ridge": lambda: make_pipeline(StandardScaler(), Ridge(alpha=10.0)),
    "random-forest": lambda: RandomForestRegressor(
        n_estimators=300, min_samples_leaf=2, random_state=42),
    "grad-boosting": lambda: HistGradientBoostingRegressor(
        max_depth=3, learning_rate=0.08, max_iter=300, random_state=42),
}


def oof_predictions(model_fn, X, y, groups):
    """Predicciones out-of-fold con GroupKFold por sujeto."""
    n_splits = min(5, len(np.unique(groups)))
    oof = np.full(len(y), np.nan)
    for tr, te in GroupKFold(n_splits=n_splits).split(X, y, groups):
        m = model_fn()
        m.fit(X.iloc[tr], y.iloc[tr])
        oof[te] = m.predict(X.iloc[te])
    return oof, n_splits


def load_split(path) -> tuple[set, set]:
    """Lee una partición fija (ver ml/subject_split_seed42.json) → (dev_ids, test_ids)."""
    d = json.loads(Path(path).read_text())
    return set(d["train_validation_subject_ids"]), set(d["test_subject_ids"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default=str(HERE / "out" / "features.csv"))
    ap.add_argument("--experiment", default="somnoai-brain-age")
    ap.add_argument("--split", default=None,
                    help="JSON con partición fija dev/test por sujeto (ej. subject_split_seed42.json). "
                         "Si se omite, la CV corre sobre todas las noches (comportamiento previo).")
    args = ap.parse_args()

    df = pd.read_csv(args.features)
    feature_names = [c for c in df.columns if c not in META_COLS]

    dev_df, test_df = df, None
    if args.split:
        dev_ids, test_ids = load_split(args.split)
        present = set(df["subject"])
        missing = (dev_ids | test_ids) - present
        if missing:
            print(f"⚠ {len(missing)} sujetos de la partición no están en {args.features} "
                  f"(dataset incompleto): {sorted(missing)[:10]}{'…' if len(missing) > 10 else ''}")
        dev_df = df[df["subject"].isin(dev_ids)].reset_index(drop=True)
        test_df = df[df["subject"].isin(test_ids)].reset_index(drop=True)
        print(f"partición fija: {len(dev_df)} noches / {dev_df['subject'].nunique()} sujetos dev · "
              f"{len(test_df)} noches / {test_df['subject'].nunique()} sujetos test")

    X, y, groups = dev_df[feature_names], dev_df["age"], dev_df["subject"].values
    n_subj = len(np.unique(groups))
    print(f"{len(dev_df)} noches · {n_subj} sujetos (dev) · {len(feature_names)} features")
    if n_subj < 10:
        print("⚠ MUESTRA PEQUEÑA: los números no son representativos; esto valida el "
              "flujo de experimentación. Corra build_features.py sobre las 153 noches "
              "para los experimentos reales.")

    mlflow.set_experiment(args.experiment)
    naive_mae = float(np.mean(np.abs(y - y.mean())))
    results = {}

    for name, model_fn in MODELS.items():
        with mlflow.start_run(run_name=name):
            oof, n_splits = oof_predictions(model_fn, X, y, groups)
            mae = mean_absolute_error(y, oof)
            rmse = float(np.sqrt(mean_squared_error(y, oof)))
            r2 = r2_score(y, oof) if len(y) > 2 else float("nan")
            bai = oof - y
            bai_corr = pearsonr(bai, y)[0] if len(y) > 2 else float("nan")

            mlflow.log_params({
                "model": name, "cv": f"GroupKFold(k={n_splits}) por sujeto",
                "n_nights": len(dev_df), "n_subjects": n_subj,
                "n_features": len(feature_names), "target": "edad (años)",
                "age_as_feature": False,
                "split": args.split or "none (CV sobre todas las noches)",
            })
            mlflow.log_metrics({
                "mae_oof": mae, "rmse_oof": rmse, "r2_oof": r2,
                "naive_mae": naive_mae,
                "bai_age_corr": bai_corr,  # ≠ 0 ⇒ falta calibrar regresión a la media
            })

            test_mae = None
            if test_df is not None and len(test_df):
                m_dev = model_fn()
                m_dev.fit(X, y)
                X_test, y_test = test_df[feature_names], test_df["age"]
                pred_test = m_dev.predict(X_test)
                test_mae = mean_absolute_error(y_test, pred_test)
                test_naive_mae = float(np.mean(np.abs(y_test - y.mean())))
                mlflow.log_metrics({
                    "mae_test_heldout": test_mae,
                    "naive_mae_test": test_naive_mae,
                    "bai_age_corr_test": pearsonr(pred_test - y_test, y_test)[0] if len(y_test) > 2 else float("nan"),
                })

            fig, ax = plt.subplots(figsize=(5, 5))
            ax.scatter(y, oof, alpha=0.7)
            lims = [min(y.min(), np.nanmin(oof)) - 5, max(y.max(), np.nanmax(oof)) + 5]
            ax.plot(lims, lims, "k--", lw=1)
            ax.set_xlabel("Edad cronológica (años)")
            ax.set_ylabel("Edad cerebral estimada OOF (años)")
            ax.set_title(f"{name} · MAE {mae:.1f} años")
            fig.tight_layout()
            mlflow.log_figure(fig, "oof_scatter.png")
            plt.close(fig)

            results[name] = mae
            test_str = f" · MAE test (una vez) {test_mae:5.1f}" if test_mae is not None else ""
            print(f"  {name:14s} MAE {mae:5.1f} · RMSE {rmse:5.1f} · R² {r2:5.2f} "
                  f"· corr(BAI,edad) {bai_corr:+.2f}{test_str}")

    if test_df is not None:
        print("\n⚠ La cifra defendible es la de CV sobre dev (mae_oof); el MAE de test se mira "
              "una sola vez por experimento y se sesga a la baja si se vuelve a consultar.")

    # ── bundle del mejor modelo, en el formato que consume la API ──
    # se reentrena con TODAS las noches disponibles (dev + test) para el artefacto de
    # producción; la métrica reportada sigue siendo la de CV sobre dev, nunca esta.
    best = min(results, key=results.get)
    final = MODELS[best]()
    final.fit(df[feature_names], df["age"])
    bundle = {
        "model": final,
        "feature_names": feature_names,
        "meta": {"version": f"{best}-v1 (CV MAE {results[best]:.1f})",
                 "typical_error": round(results[best], 1),
                 "interval_level": 0.90},
    }
    out = HERE / "out" / "model.joblib"
    joblib.dump(bundle, out)
    with mlflow.start_run(run_name=f"final-{best}"):
        mlflow.log_params({"model": best, "fitted_on": "todas las noches disponibles"})
        mlflow.log_metric("cv_mae_reference", results[best])
        mlflow.log_artifact(str(out))
    print(f"\nMejor: {best} (MAE {results[best]:.1f}) → {out}")
    print("Cuando esté entrenado con las 153 noches: "
          "cp ml/out/model.joblib backend/model_artifacts/ y reiniciar la API.")


if __name__ == "__main__":
    main()
