# API de MAIA / SomnoAI — pipeline real (MNE + YASA) + FastAPI
FROM python:3.12-slim

# libgomp1: requerido por LightGBM (dependencia de YASA)
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Los --trusted-host toleran el proxy corporativo que intercepta TLS;
# en redes normales no estorban.
COPY requirements.txt .
RUN pip install --no-cache-dir \
    --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    -r requirements.txt

COPY app ./app

# data/ y model_artifacts/ llegan como volúmenes (ver docker-compose.yml):
# los EDF demo y la BD viven fuera de la imagen, y el modelo del equipo
# se enchufa sin reconstruir.
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
