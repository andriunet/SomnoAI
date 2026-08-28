#!/bin/sh
# Arranca la API de MAIA en http://localhost:8000
cd "$(dirname "$0")"
exec ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
