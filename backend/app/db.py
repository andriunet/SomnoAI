"""Persistencia de registros: SQLite (stdlib) + JSON.

El resumen y el detalle de cada análisis se guardan como JSON; la señal de la
ventana de sueño vive aparte como .npy int16 (ver signals.py) y `signal_path`
la referencia (varios registros pueden compartirla, p. ej. clones de un demo).
"""
import json
import sqlite3
import threading
from . import config

_lock = threading.Lock()


def _conn():
    c = sqlite3.connect(config.DB_PATH)
    c.execute("""CREATE TABLE IF NOT EXISTS records(
        id TEXT PRIMARY KEY,
        analyzed_at TEXT NOT NULL,
        summary TEXT NOT NULL,
        detail TEXT NOT NULL,
        signal_path TEXT NOT NULL)""")
    return c


def insert(record_id: str, analyzed_at: str, summary: dict, detail: dict, signal_path: str):
    with _lock, _conn() as c:
        c.execute("INSERT INTO records VALUES (?,?,?,?,?)",
                  (record_id, analyzed_at, json.dumps(summary), json.dumps(detail), signal_path))


def list_summaries() -> list[dict]:
    with _lock, _conn() as c:
        rows = c.execute("SELECT summary FROM records ORDER BY analyzed_at DESC").fetchall()
    return [json.loads(r[0]) for r in rows]


def get_detail(record_id: str) -> dict | None:
    with _lock, _conn() as c:
        row = c.execute("SELECT detail FROM records WHERE id=?", (record_id,)).fetchone()
    return json.loads(row[0]) if row else None


def get_signal_path(record_id: str) -> str | None:
    with _lock, _conn() as c:
        row = c.execute("SELECT signal_path FROM records WHERE id=?", (record_id,)).fetchone()
    return row[0] if row else None


def count() -> int:
    with _lock, _conn() as c:
        return c.execute("SELECT COUNT(*) FROM records").fetchone()[0]


def delete(record_id: str) -> str | None:
    """Borra el registro y devuelve su signal_path SOLO si ningún otro registro
    lo comparte (los clones de los demos reutilizan la señal del original)."""
    with _lock, _conn() as c:
        row = c.execute("SELECT signal_path FROM records WHERE id=?", (record_id,)).fetchone()
        if not row:
            return None
        c.execute("DELETE FROM records WHERE id=?", (record_id,))
        still = c.execute("SELECT COUNT(*) FROM records WHERE signal_path=?", (row[0],)).fetchone()[0]
        return row[0] if still == 0 else ""
