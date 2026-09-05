"""CV de hiperparámetros para Gradient Boosting, registrada en MLflow.

El bake-off inicial (ml/train.py, Ridge vs. Random Forest vs. Gradient
Boosting) corrió Gradient Boosting con una configuración fija sin buscar
hiperparámetros (max_depth=3, learning_rate=0.08, max_iter=300) y quedó
prácticamente empatado con Ridge en CV (10.81 vs. 10.77 años de MAE). Antes
de afirmar que Gradient Boosting es mejor que la línea base hace falta darle
la misma oportunidad que tuvo Ridge: un barrido real de hiperparámetros sobre
la partición fija del equipo (ml/subject_split_seed42.json), con el mismo
criterio de selección (menor MAE de CV entre las combinaciones que baten la
media y controlan la regresión a la media, |corr(BAI, edad)| por debajo de un
umbral).

Uso:
    # contra el tracking server del equipo (si está arriba)
    MLFLOW_TRACKING_URI=http://3.236.12.125:8050 \
        ./backend/.venv/bin/python ml/tune_gb.py

    # local, si el EC2 no responde
    MLFLOW_TRACKING_URI=sqlite:///ml/mlserver/mlflow_gb.db \
        ./backend/.venv/bin/python ml/tune_gb.py

El bundle del mejor modelo (reentrenado con dev+test, formato que consume la
API) queda en ml/out/model_gb_cv.joblib.
"""
import argparse
import itertools
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from train import META_COLS, load_split, oof_predictions

HERE = Path(__file__).parent


def gb_fn(max_depth, learning_rate, max_iter):
    return lambda: HistGradientBoostingRegressor(
        max_depth=max_depth, learning_rate=learning_rate, max_iter=max_iter,
        random_state=42)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", default=str(HERE / "out" / "features_full.csv"))
    ap.add_argument("--split", default=str(HERE / "subject_split_seed42.json"))
    ap.add_argument("--experiment", default="edad-cerebral-Diego-GB-CV")
    ap.add_argument("--max-depths", default="2,3,4")
    ap.add_argument("--learning-rates",
                     default=",".join(f"{lr:g}" for lr in np.logspace(-2, -0.3, 7)))
    ap.add_argument("--max-iters", default="100,200,300,500")
    ap.add_argument("--bai-corr-max", type=float, default=0.5,
                     help="mismo criterio que tune_ridge.py: entre las combinaciones que "
                          "baten la línea base, se prefiere la de menor MAE de CV con "
                          "|corr(BAI,edad)| por debajo de este umbral")
    args = ap.parse_args()

    df = pd.read_csv(args.features)
    feature_names = [c for c in df.columns if c not in META_COLS]
    dev_ids, test_ids = load_split(args.split)
    dev_df = df[df["subject"].isin(dev_ids)].reset_index(drop=True)
    test_df = df[df["subject"].isin(test_ids)].reset_index(drop=True)

    X, y, groups = dev_df[feature_names], dev_df["age"], dev_df["subject"].values
    n_subj = len(np.unique(groups))
    print(f"partición fija: {len(dev_df)} noches / {n_subj} sujetos dev · "
          f"{len(test_df)} noches / {test_df['subject'].nunique()} sujetos test · "
          f"{len(feature_names)} features")

    naive_mae = float(np.mean(np.abs(y - y.mean())))
    max_depths = [int(d) for d in args.max_depths.split(",")]
    learning_rates = [float(lr) for lr in args.learning_rates.split(",")]
    max_iters = [int(m) for m in args.max_iters.split(",")]
    grid_specs = list(itertools.product(max_depths, learning_rates, max_iters))
    print(f"rejilla: {len(max_depths)} x {len(learning_rates)} x {len(max_iters)} "
          f"= {len(grid_specs)} combinaciones")

    mlflow.set_experiment(args.experiment)
    grid_rows = []

    for i, (max_depth, lr, max_iter) in enumerate(grid_specs, 1):
        with mlflow.start_run(run_name=f"gb depth={max_depth} lr={lr:g} iter={max_iter}"):
            oof, n_splits = oof_predictions(gb_fn(max_depth, lr, max_iter), X, y, groups)
            mae = mean_absolute_error(y, oof)
            rmse = float(np.sqrt(mean_squared_error(y, oof)))
            r2 = r2_score(y, oof) if len(y) > 2 else float("nan")
            bai_corr = pearsonr(oof - y, y)[0] if len(y) > 2 else float("nan")
            beats_naive = mae < naive_mae

            mlflow.log_params({
                "model": "grad-boosting", "max_depth": max_depth, "learning_rate": lr,
                "max_iter": max_iter,
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
            grid_rows.append({"max_depth": max_depth, "learning_rate": lr, "max_iter": max_iter,
                               "mae_oof": mae, "rmse_oof": rmse, "r2_oof": r2,
                               "bai_age_corr": bai_corr, "beats_naive": beats_naive})
            flag = "" if beats_naive else "  ✗ no bate la media"
            print(f"  [{i:3d}/{len(grid_specs)}] depth={max_depth} lr={lr:6.4g} "
                  f"iter={max_iter:4d}  MAE {mae:5.2f}  RMSE {rmse:5.2f}  R² {r2:5.2f}  "
                  f"corr(BAI,edad) {bai_corr:+.2f}{flag}")

    grid = pd.DataFrame(grid_rows)

    eligible = grid[grid.beats_naive & (grid.bai_age_corr.abs() < args.bai_corr_max)]
    if eligible.empty:
        eligible = grid[grid.beats_naive]
    if eligible.empty:
        eligible = grid
    best = eligible.loc[eligible.mae_oof.idxmin()]
    best_depth, best_lr, best_iter = int(best.max_depth), float(best.learning_rate), int(best.max_iter)
    print(f"\nMejor combinación: depth={best_depth} lr={best_lr:g} iter={best_iter} "
          f"(MAE CV {best.mae_oof:.2f}, corr(BAI,edad) {best.bai_age_corr:+.2f})")
    print(f"Referencia (config. fija del bake-off inicial, depth=3 lr=0.08 iter=300): "
          f"MAE CV ~10.81")

    fig, axes = plt.subplots(1, len(max_depths), figsize=(4.2 * len(max_depths), 4), sharey=True)
    if len(max_depths) == 1:
        axes = [axes]
    for ax, depth in zip(axes, max_depths):
        sub = grid[grid.max_depth == depth]
        for max_iter in max_iters:
            s = sub[sub.max_iter == max_iter].sort_values("learning_rate")
            ax.plot(s.learning_rate, s.mae_oof, "o-", lw=1.3, ms=3, label=f"iter={max_iter}")
        ax.axhline(naive_mae, ls="--", c="gray", lw=1, label="línea base (media)" if depth == max_depths[0] else None)
        ax.set_xscale("log")
        ax.set_xlabel("learning_rate")
        ax.set_title(f"max_depth={depth}")
    axes[0].set_ylabel("MAE CV (años)")
    axes[-1].legend(fontsize=8)
    fig.suptitle("Gradient Boosting · CV de hiperparámetros agrupada por sujeto")
    fig.tight_layout()

    grid_csv = HERE / "out" / "gb_cv_grid.csv"
    grid_csv.parent.mkdir(parents=True, exist_ok=True)
    grid.to_csv(grid_csv, index=False)

    with mlflow.start_run(run_name=f"gb-best depth={best_depth} lr={best_lr:g} iter={best_iter}"):
        mlflow.log_params({
            "model": "grad-boosting", "max_depth": best_depth, "learning_rate": best_lr,
            "max_iter": best_iter,
            "selection_criterion": f"menor MAE CV entre las que baten la media y "
                                    f"|corr(BAI,edad)|<{args.bai_corr_max}",
            "n_combinations_probadas": len(grid_specs),
        })
        mlflow.log_metrics({
            "mae_oof": best.mae_oof, "rmse_oof": best.rmse_oof, "r2_oof": best.r2_oof,
            "bai_age_corr": best.bai_age_corr, "naive_mae": naive_mae,
        })
        mlflow.log_figure(fig, "gb_hparam_sweep.png")
        mlflow.log_artifact(str(grid_csv))
        plt.close(fig)

        m_dev = gb_fn(best_depth, best_lr, best_iter)()
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

        final = gb_fn(best_depth, best_lr, best_iter)()
        final.fit(df[feature_names], df["age"])
        bundle = {
            "model": final,
            "feature_names": feature_names,
            "meta": {"version": f"gb-cv-v1 (depth={best_depth}, lr={best_lr:g}, "
                                 f"iter={best_iter}, CV MAE {best.mae_oof:.1f})",
                     "typical_error": round(float(best.mae_oof), 1),
                     "interval_level": 0.90},
        }
        out = HERE / "out" / "model_gb_cv.joblib"
        joblib.dump(bundle, out)
        mlflow.log_artifact(str(out))

    test_str = f" · MAE test (una vez) {test_mae:.2f}" if test_mae is not None else ""
    print(f"\n⚠ La cifra defendible es mae_oof (CV sobre dev); el MAE de test se mira una "
          f"sola vez.{test_str}")
    print(f"Bundle → {HERE / 'out' / 'model_gb_cv.joblib'}")


if __name__ == "__main__":
    main()
