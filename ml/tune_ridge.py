"""CV de hiperparámetros para Ridge, registrada en MLflow.

Ridge es la línea base del proyecto y, según el bake-off de ocho familias de
modelos que corrió el compañero Sebastián (`Experimentos/Sebastian/README.md`
en el repo del equipo, y el experimento `edad-cerebral-sebastian` en MLflow),
nada la superó con 62 sujetos de desarrollo — el resto perdió por varianza, no
por sesgo. Este script itera sobre ESE modelo: un barrido de `alpha` para
Ridge, con la misma partición fija por sujeto (`ml/subject_split_seed42.json`)
y la misma rejilla logarítmica de 13 valores (1e-2 … 1e4) que usó Sebastián,
para que los números sean comparables entre experimentos del equipo. La
selección del mejor alpha usa su mismo criterio: menor MAE de CV entre los
que baten la media Y mantienen |corr(BAI, edad)| por debajo de un umbral
(evidencia de que no está sobre-corrigiendo la regresión a la media).

Uso:
    # contra el tracking server del equipo
    MLFLOW_TRACKING_URI=http://13.223.193.36:8050 \
        ./backend/.venv/bin/python ml/tune_ridge.py

    # rejilla / umbral / features distintos
    ./backend/.venv/bin/python ml/tune_ridge.py \
        --alphas 1,10,100 --bai-corr-max 0.4 --features ml/out/features_full.csv

El bundle del mejor alpha (reentrenado con dev+test, formato que consume la
API) queda en ml/out/model_ridge_cv.joblib — para promoverlo:
    cp ml/out/model_ridge_cv.joblib backend/model_artifacts/model.joblib
"""
import argparse
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from train import META_COLS, load_split, oof_predictions

HERE = Path(__file__).parent


def ridge_fn(alpha):
    return lambda: make_pipeline(StandardScaler(), Ridge(alpha=alpha))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default=str(HERE / "out" / "features_full.csv"))
    ap.add_argument("--split", default=str(HERE / "subject_split_seed42.json"))
    ap.add_argument("--experiment", default="edad-cerebral-Diego-Ridge-CV")
    ap.add_argument("--alphas", default=",".join(f"{a:g}" for a in np.logspace(-2, 4, 13)),
                     help="alphas de Ridge a barrer, separados por coma (por defecto, la misma "
                          "rejilla log de 13 valores 1e-2..1e4 que usó Experimentos/Sebastian)")
    ap.add_argument("--bai-corr-max", type=float, default=0.5,
                     help="criterio de selección (igual que Experimentos/Sebastian): entre los "
                          "alphas que baten la línea base, se prefiere el de menor MAE de CV con "
                          "|corr(BAI,edad)| por debajo de este umbral")
    args = ap.parse_args()

    df = pd.read_csv(args.features)
    feature_names = [c for c in df.columns if c not in META_COLS]
    dev_ids, test_ids = load_split(args.split)
    present = set(df["subject"])
    missing = (dev_ids | test_ids) - present
    if missing:
        print(f"⚠ {len(missing)} sujetos de la partición no están en {args.features}: "
              f"{sorted(missing)[:10]}{'…' if len(missing) > 10 else ''}")
    dev_df = df[df["subject"].isin(dev_ids)].reset_index(drop=True)
    test_df = df[df["subject"].isin(test_ids)].reset_index(drop=True)

    X, y, groups = dev_df[feature_names], dev_df["age"], dev_df["subject"].values
    n_subj = len(np.unique(groups))
    print(f"partición fija: {len(dev_df)} noches / {n_subj} sujetos dev · "
          f"{len(test_df)} noches / {test_df['subject'].nunique()} sujetos test · "
          f"{len(feature_names)} features")

    naive_mae = float(np.mean(np.abs(y - y.mean())))
    alphas = [float(a) for a in args.alphas.split(",")]

    mlflow.set_experiment(args.experiment)
    grid_rows = []

    for alpha in alphas:
        with mlflow.start_run(run_name=f"ridge alpha={alpha:g}"):
            oof, n_splits = oof_predictions(ridge_fn(alpha), X, y, groups)
            mae = mean_absolute_error(y, oof)
            rmse = float(np.sqrt(mean_squared_error(y, oof)))
            r2 = r2_score(y, oof) if len(y) > 2 else float("nan")
            bai_corr = pearsonr(oof - y, y)[0] if len(y) > 2 else float("nan")
            beats_naive = mae < naive_mae

            mlflow.log_params({
                "model": "ridge", "alpha": alpha, "scaler": "StandardScaler",
                "cv": f"GroupKFold(k={n_splits}) por sujeto",
                "n_nights": len(dev_df), "n_subjects": n_subj,
                "n_features": len(feature_names), "target": "edad (años)",
                "age_as_feature": False, "split": args.split,
            })
            mlflow.log_metrics({
                "mae_oof": mae, "rmse_oof": rmse, "r2_oof": r2,
                "naive_mae": naive_mae, "bai_age_corr": bai_corr,
                "abs_bai_age_corr": abs(bai_corr), "beats_naive": float(beats_naive),
            })
            grid_rows.append({"alpha": alpha, "mae_oof": mae, "rmse_oof": rmse, "r2_oof": r2,
                               "bai_age_corr": bai_corr, "beats_naive": beats_naive})
            flag = "" if beats_naive else "  ✗ no bate la media"
            print(f"  alpha={alpha:9.4g}  MAE {mae:5.2f}  RMSE {rmse:5.2f}  R² {r2:5.2f}  "
                  f"corr(BAI,edad) {bai_corr:+.2f}{flag}")

    grid = pd.DataFrame(grid_rows)

    # mismo criterio de selección que Experimentos/Sebastian: entre los alphas que
    # baten la media Y controlan la regresión a la media (|corr(BAI,edad)| < umbral),
    # el de menor MAE de CV; si ninguno cumple el umbral, cae al de menor MAE entre
    # los que baten la media; si ninguno bate la media, el de menor MAE de toda la grilla.
    eligible = grid[grid.beats_naive & (grid.bai_age_corr.abs() < args.bai_corr_max)]
    if eligible.empty:
        eligible = grid[grid.beats_naive]
    if eligible.empty:
        eligible = grid
    best = eligible.loc[eligible.mae_oof.idxmin()]
    best_alpha = float(best.alpha)
    print(f"\nMejor alpha: {best_alpha:g} (MAE CV {best.mae_oof:.2f}, "
          f"corr(BAI,edad) {best.bai_age_corr:+.2f})")

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(grid.alpha, grid.mae_oof, "o-", label="MAE CV (dev)")
    ax.axhline(naive_mae, ls="--", c="gray", label="línea base (media)")
    ax.axvline(best_alpha, ls=":", c="red", label=f"mejor α={best_alpha:g}")
    ax.set_xscale("log")
    ax.set_xlabel("alpha (Ridge)")
    ax.set_ylabel("MAE (años)")
    ax.set_title("Ridge · CV de hiperparámetros agrupada por sujeto")
    ax.legend()
    fig.tight_layout()

    grid_csv = HERE / "out" / "ridge_cv_grid.csv"
    grid_csv.parent.mkdir(parents=True, exist_ok=True)
    grid.to_csv(grid_csv, index=False)

    with mlflow.start_run(run_name=f"ridge-best alpha={best_alpha:g}"):
        mlflow.log_params({
            "model": "ridge", "alpha": best_alpha,
            "selection_criterion": f"menor MAE CV entre los que baten la media y "
                                    f"|corr(BAI,edad)|<{args.bai_corr_max}",
            "alphas_probados": args.alphas,
        })
        mlflow.log_metrics({
            "mae_oof": best.mae_oof, "rmse_oof": best.rmse_oof, "r2_oof": best.r2_oof,
            "bai_age_corr": best.bai_age_corr, "naive_mae": naive_mae,
        })
        mlflow.log_figure(fig, "ridge_alpha_sweep.png")
        mlflow.log_artifact(str(grid_csv))
        plt.close(fig)

        m_dev = ridge_fn(best_alpha)()
        m_dev.fit(X, y)
        test_mae = test_naive = test_bai_corr = None
        if len(test_df):
            X_test, y_test = test_df[feature_names], test_df["age"]
            pred_test = m_dev.predict(X_test)
            test_mae = mean_absolute_error(y_test, pred_test)
            test_naive = float(np.mean(np.abs(y_test - y.mean())))
            test_bai_corr = pearsonr(pred_test - y_test, y_test)[0] if len(y_test) > 2 else float("nan")
            mlflow.log_metrics({
                "mae_test_heldout": test_mae, "naive_mae_test": test_naive,
                "bai_age_corr_test": test_bai_corr,
            })

        final = ridge_fn(best_alpha)()
        final.fit(df[feature_names], df["age"])
        bundle = {
            "model": final,
            "feature_names": feature_names,
            "meta": {"version": f"ridge-cv-v1 (alpha={best_alpha:g}, CV MAE {best.mae_oof:.1f})",
                     "typical_error": round(float(best.mae_oof), 1),
                     "interval_level": 0.90},
        }
        out = HERE / "out" / "model_ridge_cv.joblib"
        joblib.dump(bundle, out)
        mlflow.log_artifact(str(out))

    test_str = f" · MAE test (una vez) {test_mae:.2f}" if test_mae is not None else ""
    print(f"\n⚠ La cifra defendible es mae_oof (CV sobre dev); el MAE de test se mira una "
          f"sola vez.{test_str}")
    print(f"Bundle → {HERE / 'out' / 'model_ridge_cv.joblib'}")
    print("Para promoverlo a la API: "
          "cp ml/out/model_ridge_cv.joblib backend/model_artifacts/model.joblib")


if __name__ == "__main__":
    main()
