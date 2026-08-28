"""Construye la tabla de features para entrenar, usando EL MISMO pipeline de la API.

Esto garantiza la regla de oro: lo que ve el modelo en entrenamiento es
idéntico a lo que ve en inferencia (mismo recorte de vigilia, mismas bandas,
mismos nombres de feature).

Uso:
    ./backend/.venv/bin/python ml/build_features.py --data-dir backend/data/demo
    ./backend/.venv/bin/python ml/build_features.py --data-dir <carpeta con las 153 noches>

Entrada:  carpeta con pares de Sleep-EDFx  SC4ssN??-PSG.edf + SC4ssN??-Hypnogram.edf
          (la edad y el sexo salen de ml/age_records.csv, el índice oficial del dataset)
Salida:   ml/out/features.csv  (una fila por noche: metadatos + features)
"""
import argparse
import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.pipeline import analysis  # noqa: E402  (usa el pipeline real de la API)


class _StubPredictor:
    """El pipeline pide un predictor; para extraer features basta un stub."""
    @staticmethod
    def predict(features):
        return 0.0, {"version": "features-only", "typical_error": 0.0, "interval_level": 0.9}


def load_index() -> dict:
    """fname del PSG → (subject, night, age, sex) según el índice del dataset."""
    idx = {}
    with open(Path(__file__).parent / "age_records.csv") as fh:
        for row in csv.DictReader(fh):
            if row["record type"] == "PSG":
                idx[row["fname"]] = {
                    "subject": int(row["subject"]),
                    "night": int(row["night"]),
                    "age": int(row["age"]),
                    "sex": "F" if row["sex"] == "female" else "M",
                }
    return idx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", required=True, help="carpeta con los pares PSG+Hypnogram")
    ap.add_argument("--out", default=str(Path(__file__).parent / "out" / "features.csv"))
    args = ap.parse_args()

    data_dir = Path(args.data_dir)
    index = load_index()
    psgs = sorted(data_dir.glob("SC4*-PSG.edf"))
    if not psgs:
        sys.exit(f"No hay archivos SC4*-PSG.edf en {data_dir}")

    rows, feature_names = [], None
    t_start = time.time()
    for k, psg in enumerate(psgs, 1):
        meta = index.get(psg.name)
        if meta is None:
            print(f"  ⚠ {psg.name}: no está en age_records.csv, se omite")
            continue
        # el hipnograma comparte el prefijo SC4ssN con el PSG
        hyps = list(data_dir.glob(psg.name[:6] + "*-Hypnogram.edf"))
        if not hyps:
            print(f"  ⚠ {psg.name}: sin hipnograma, se omite (entrenar exige el anotado)")
            continue
        try:
            _, detail, _, _ = analysis.run_analysis(
                str(psg), str(hyps[0]), file_name=psg.name,
                size_mb=psg.stat().st_size / 1048576,
                chronological_age=meta["age"], sex=meta["sex"],
                subject_code=f"SC{meta['subject']:02d}", predictor=_StubPredictor)
        except Exception as e:
            print(f"  ⚠ {psg.name}: falló el pipeline ({e}), se omite")
            continue
        feats = detail["features"]
        feature_names = feature_names or sorted(feats)
        rows.append({"fname": psg.name, "subject": meta["subject"], "night": meta["night"],
                     "age": meta["age"], "sex": meta["sex"],
                     **{k2: feats.get(k2, 0.0) for k2 in feature_names}})
        print(f"  [{k}/{len(psgs)}] {psg.name} · sujeto {meta['subject']:02d} · edad {meta['age']}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["fname", "subject", "night", "age", "sex"] + feature_names)
        w.writeheader()
        w.writerows(rows)
    print(f"\n{len(rows)} noches → {out} · {len(feature_names)} features · "
          f"{time.time() - t_start:.0f}s")


if __name__ == "__main__":
    main()
