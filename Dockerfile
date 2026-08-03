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

# Hugging Face Spaces serve on 7860; Render/Fly inject $PORT. Honour $PORT,
# else default to 7860 (works on HF out of the box).
EXPOSE 7860
CMD ["sh", "-c", "uvicorn src.app:app --host 0.0.0.0 --port ${PORT:-7860}"]
