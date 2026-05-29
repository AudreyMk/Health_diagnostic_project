import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

# Bases de données
PG_DSN = os.getenv("PG_DSN", "postgresql://medrag:medrag_2024@localhost:5432/medrag")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://medrag:medrag_2024@localhost:27017/")
MONGO_DB = "medrag"
MONGO_COLL = "health_centers"

# Modèle d'embedding (même que load_to_databases.py)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")

# LLM Claude
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# Paramètres RAG — retrieval à 3 pools
TOP_K = int(os.getenv("TOP_K", "8"))
TOP_K_PATHOLOGIES = int(os.getenv("TOP_K_PATHOLOGIES", "4"))   # pool 1 : pathologies
TOP_K_PATIENTS    = int(os.getenv("TOP_K_PATIENTS", "3"))       # pool 2 : patients
TOP_K_CLINICAL    = int(os.getenv("TOP_K_CLINICAL", "2"))       # pool 3 : mtsamples
TOP_K_CENTERS = int(os.getenv("TOP_K_CENTERS", "5"))
MAX_DISTANCE_METERS = int(os.getenv("MAX_DISTANCE_METERS", "20000"))
MIN_SIMILARITY = float(os.getenv("MIN_SIMILARITY", "0.25"))
AGE_RANGE = int(os.getenv("AGE_RANGE", "15"))                   # filtre démographique ± ans

# Pool PostgreSQL (psycopg3)
PG_POOL_MIN = int(os.getenv("PG_POOL_MIN", "2"))
PG_POOL_MAX = int(os.getenv("PG_POOL_MAX", "10"))

# API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
