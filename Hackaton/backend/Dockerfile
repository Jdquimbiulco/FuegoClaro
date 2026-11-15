# Backend FuegoClaro — FastAPI + Pandas/NumPy/Shapely
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend \
    MALLOC_ARENA_MAX=2 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1

WORKDIR /app

# CA certificates para HTTPS y libgomp para scikit-learn/HistGradientBoosting.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Dependencias primero para aprovechar la caché de capas.
COPY backend/requirements.txt backend/requirements-dev.txt /app/backend/
RUN pip install --no-cache-dir \
    -r /app/backend/requirements.txt \
    -r /app/backend/requirements-dev.txt

# Código, scripts, pruebas y datos.
COPY backend /app/backend
COPY scripts /app/scripts
COPY tests /app/tests
COPY pytest.ini /app/pytest.ini
COPY data /app/data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
