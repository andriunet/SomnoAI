"""API de MAIA / SomnoAI — implementa docs/API_CONTRACT.md.

Arranque:  ./run.sh   (equivale a: uvicorn app.main:app --port 8000)
Al primer arranque precomputa los 3 demos con los EDF reales de data/demo/.
"""
import logging
import re
import secrets
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Depends, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import config, db, signals
from .model import predictor
from .pipeline import analysis, edf_io

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("maia.api")

_TOKENS: set[str] = set()
_USER = {"name": "Superusuario", "initials": "SU"}


def _err(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


# ── precómputo de demos ───────────────────────────────────────────────
def _precompute_demos():
    for demo_id, meta in config.DEMOS.items():
        rec_id = f"demo-{demo_id}"
        if db.get_detail(rec_id):
            continue
        psg = config.DEMO_DIR / meta["psg"]
        hyp = config.DEMO_DIR / meta["hyp"]
        if not psg.exists():
            log.warning("Demo %s: falta %s (¿descarga incompleta?)", demo_id, psg.name)
            continue
        log.info("Precomputando demo %s…", demo_id)
        summary, detail, sig, sfreq = analysis.run_analysis(
            str(psg), str(hyp) if hyp.exists() else None,
            file_name=meta["psg"], size_mb=psg.stat().st_size / 1048576,
            chronological_age=meta["age"], sex=meta["sex"], subject_code=meta["subject"],
            predictor=predictor)
        summary["age_source"] = "dataset-index"
        sig_path = config.STORE_DIR / f"{rec_id}.npy"
        signals.save(sig_path, sig)
        _insert(rec_id, summary, detail, str(sig_path))
        log.info("Demo %s listo: edad cerebral %.1f (BAI %+.1f)",
                 demo_id, summary["brain_age"], summary["bai"])


def _insert(rec_id: str, summary: dict, detail_extra: dict, sig_path: str) -> dict:
    analyzed_at = _now()
    summary = {"id": rec_id, "analyzed_at": analyzed_at, **summary}
    full_detail = {**summary, **detail_extra}
    db.insert(rec_id, analyzed_at, summary, full_detail, sig_path)
    return full_detail


@asynccontextmanager
async def lifespan(app: FastAPI):
    _precompute_demos()
    log.info("MAIA API lista · %d registros en la base", db.count())
    yield


app = FastAPI(title="MAIA / SomnoAI API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(HTTPException)
async def http_exc(_, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "error", "message": str(exc.detail)}
    return JSONResponse(status_code=exc.status_code, content={"error": detail})


@app.get("/api/v1/health")
def health():
    """Sin auth: para el healthcheck de Docker Compose y monitoreo."""
    return {"status": "ok", "records": db.count(),
            "model": predictor.active_version()}


# ── auth ──────────────────────────────────────────────────────────────
class LoginBody(BaseModel):
    username: str
    password: str


@app.post("/api/v1/auth/login")
def login(body: LoginBody):
    if body.username.strip() == config.USERNAME and body.password == config.PASSWORD:
        token = secrets.token_hex(16)
        _TOKENS.add(token)
        return {"token": token, "user": _USER}
    raise _err(401, "invalid_credentials", "Usuario o contraseña incorrectos.")


def auth(authorization: str = Header(default="")) -> str:
    token = authorization.removeprefix("Bearer ").strip()
    if token not in _TOKENS:
        raise _err(401, "unauthorized", "La sesión expiró. Inicie sesión de nuevo.")
    return token


# ── registros ─────────────────────────────────────────────────────────
@app.get("/api/v1/records")
def list_records(_: str = Depends(auth)):
    return {"records": db.list_summaries()}


@app.get("/api/v1/records/{record_id}")
def get_record(record_id: str, _: str = Depends(auth)):
    detail = db.get_detail(record_id)
    if not detail:
        raise _err(404, "not_found", "El registro no existe.")
    return detail


@app.delete("/api/v1/records/{record_id}")
def delete_record(record_id: str, _: str = Depends(auth)):
    sig_path = db.delete(record_id)
    if sig_path is None:
        raise _err(404, "not_found", "El registro no existe.")
    if sig_path:  # "" = otra fila aún comparte la señal (clones de demos)
        Path(sig_path).unlink(missing_ok=True)
    return {"deleted": record_id}


# ── análisis ──────────────────────────────────────────────────────────
@app.post("/api/v1/predict")
def predict(file: UploadFile, chronological_age: int | None = Form(None), _: str = Depends(auth)):
    if chronological_age is not None and not (1 <= chronological_age <= 120):
        raise _err(422, "invalid_age", "La edad cronológica debe estar entre 1 y 120 años.")
    name = Path(file.filename or "registro.edf").name
    if not re.search(r"\.(edf|zip)$", name, re.I):
        raise _err(422, "invalid_file", "Formato no aceptado: cargue un .edf o un .zip.")

    tmpdir = tempfile.mkdtemp(prefix="maia_up_")
    tmp_path = Path(tmpdir) / name
    size = 0
    with open(tmp_path, "wb") as out:
        while chunk := file.file.read(1 << 20):
            size += len(chunk)
            if size > config.MAX_UPLOAD_MB * 1048576:
                raise _err(413, "too_large", f"El archivo supera el límite de {config.MAX_UPLOAD_MB} MB.")
            out.write(chunk)

    try:
        if name.lower().endswith(".zip"):
            psg_path, hyp_path, psg_name = edf_io.extract_zip(str(tmp_path))
        else:
            psg_path, hyp_path, psg_name = str(tmp_path), None, name

        # edad: la ingresada manda; si no viene, se detecta del encabezado EDF
        header = edf_io.read_subject_header(psg_path)
        if chronological_age is not None:
            age, age_source = chronological_age, "manual"
        elif header["age"] is not None:
            age, age_source = header["age"], "edf-header"
        else:
            raise _err(422, "age_required",
                       "El encabezado del EDF no trae la edad del sujeto: "
                       "ingrese la edad cronológica manualmente.")

        summary, detail, sig, sfreq = analysis.run_analysis(
            psg_path, hyp_path, file_name=psg_name, size_mb=size / 1048576,
            chronological_age=age, sex=header["sex"], subject_code=None,
            predictor=predictor)
        summary["age_source"] = age_source
    except (edf_io.InvalidFile, predictor.ArchivoInvalido) as e:
        raise _err(422, "invalid_file", str(e))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    rec_id = uuid.uuid4().hex[:12]
    sig_path = config.STORE_DIR / f"{rec_id}.npy"
    signals.save(sig_path, sig)
    return _insert(rec_id, summary, detail, str(sig_path))


class DemoBody(BaseModel):
    demo_id: str


@app.post("/api/v1/predict-demo")
def predict_demo(body: DemoBody, _: str = Depends(auth)):
    if body.demo_id not in config.DEMOS:
        raise _err(404, "not_found", "Registro demo desconocido.")
    base = db.get_detail(f"demo-{body.demo_id}")
    sig_path = db.get_signal_path(f"demo-{body.demo_id}")
    if not base:
        raise _err(503, "demo_not_ready",
                   "El registro demo aún no está precomputado en el servidor.")
    # clon instantáneo: mismo resultado, nuevo id y marca de tiempo (misma señal)
    rec_id = uuid.uuid4().hex[:12]
    summary_keys = ["subject_code", "file_name", "sex", "chronological_age", "brain_age",
                    "bai", "over_threshold", "model_version", "staging_source", "age_source"]
    # .get: tolera registros guardados por versiones previas del esquema
    summary = {k: base.get(k) for k in summary_keys}
    detail_extra = {k: v for k, v in base.items()
                    if k not in summary and k not in ("id", "analyzed_at")}
    return _insert(rec_id, summary, detail_extra, sig_path)


# ── señal por ventana ─────────────────────────────────────────────────
@app.get("/api/v1/records/{record_id}/signal")
def get_signal(record_id: str, start_s: float, duration_s: float, points: int = 1014,
               _: str = Depends(auth)):
    detail = db.get_detail(record_id)
    sig_path = db.get_signal_path(record_id)
    if not detail or not sig_path or not Path(sig_path).exists():
        raise _err(404, "not_found", "El registro no existe.")
    if not (1 <= points <= 4000) or duration_s <= 0:
        raise _err(422, "out_of_range", "Parámetros de ventana inválidos.")
    window_s = detail["night"]["window_s"]
    start_s = max(0.0, min(start_s, window_s))
    duration_s = min(duration_s, window_s - start_s) or 1.0
    sfreq = detail["quality"]["file"]["sampling_hz"]
    mins, maxs = signals.envelope(sig_path, sfreq, start_s, duration_s, points)
    return {"start_s": start_s, "duration_s": duration_s, "points": points,
            "unit": "µV", "min": mins, "max": maxs}
