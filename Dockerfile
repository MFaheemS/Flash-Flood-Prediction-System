# Backend (FastAPI) image for FloodWatch.
FROM python:3.11-slim

WORKDIR /app

# System deps some wheels need (shap/numba, shapely)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

# App code + the runtime artifacts the API actually loads
COPY config.yaml .
COPY src/ ./src/
COPY models/ ./models/
COPY data/ ./data/

EXPOSE 8000
# Render/Fly provide $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn src.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
