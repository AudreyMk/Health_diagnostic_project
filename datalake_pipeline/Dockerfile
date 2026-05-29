FROM python:3.11-slim

WORKDIR /app

# Dépendances système pour psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements_rag.txt .
RUN pip install --no-cache-dir -r requirements_rag.txt

# Pré-télécharger le modèle d'embedding au build (couche cachée)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"

COPY rag_engine/ ./rag_engine/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

CMD ["uvicorn", "rag_engine.api:app", "--host", "0.0.0.0", "--port", "8000"]
