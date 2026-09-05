# API de MAIA / SomnoAI — FastAPI + el modelo empaquetado (edad_cerebral)
#
# OJO: el contexto de construcción es la RAÍZ del repositorio, no backend/.
# Hace falta para que `model-pkg/` entre en el contexto: requirements.txt
# instala el wheel desde ahí. Ver docker-compose.yml.
FROM python:3.12-slim

# Sin dependencias de sistema: libgomp1 estaba para LightGBM, que entraba por YASA,
# y la estadificación automática ya no se usa (el modelo exige hipnograma anotado).

WORKDIR /app

# El wheel se copia ANTES de instalar: es la primera línea de requirements.txt.
COPY backend/requirements.txt .
COPY model-pkg/ ./model-pkg/

# Los --trusted-host toleran el proxy corporativo que intercepta TLS;
# en redes normales no estorban.
RUN pip install --no-cache-dir \
    --trusted-host pypi.org --trusted-host files.pythonhosted.org \
    -r requirements.txt

COPY backend/app ./app

# data/ llega como volumen (ver docker-compose.yml): la base de datos y las
# señales viven fuera de la imagen. El modelo ya NO se monta: viaja en el wheel.
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
