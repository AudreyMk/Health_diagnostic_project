"""
API REST MedRAG — FastAPI

Endpoints :
  POST /api/suggest          Suggérer des pathologies à partir de symptômes
  GET  /api/centers          Trouver les centres de santé proches
  GET  /api/pathologies      Lister toutes les pathologies indexées
  GET  /api/health           État de l'API et des bases de données
"""
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .config import API_HOST, API_PORT
from .embedding_manager import EmbeddingManager
from .retriever import PGRetriever, MongoRetriever
from .llm_client import LLMClient
from .rag_engine import MedRAGEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan : initialisation unique des ressources
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== Démarrage MedRAG API ===")
    try:
        embedder = EmbeddingManager()
        pg = PGRetriever()
        mongo = MongoRetriever()
        llm = LLMClient()
        app.state.engine = MedRAGEngine(embedder=embedder, pg=pg, mongo=mongo, llm=llm)
        app.state.pg = pg
        app.state.mongo = mongo
        logger.info("=== MedRAG API prête ===")
    except Exception as e:
        logger.error(f"Erreur d'initialisation : {e}")
        raise
    yield
    logger.info("Arrêt de MedRAG API — fermeture des connexions")
    app.state.engine.close()


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MedRAG API",
    description=(
        "API d'aide à la décision clinique basée sur RAG (Retrieval-Augmented Generation). "
        "Analyse des symptômes et suggère des hypothèses diagnostiques en s'appuyant sur "
        "DDXPlus FR (49 pathologies, 1,3M cas synthétiques) et les centres de santé FINESS."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Modèles Pydantic
# ---------------------------------------------------------------------------

class SuggestRequest(BaseModel):
    symptoms: str = Field(
        ...,
        min_length=10,
        description="Description des symptômes en texte libre (français de préférence)",
        examples=["Fièvre à 39°C depuis 3 jours, toux sèche, douleurs thoraciques"],
    )
    age: Optional[int] = Field(None, ge=0, le=120, description="Âge du patient en années")
    sex: Optional[str] = Field(None, description="Sexe du patient : M (Homme) ou F (Femme)")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Latitude GPS (pour centres proches)")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Longitude GPS")
    top_k: int = Field(8, ge=1, le=20, description="Nombre de documents à récupérer")
    top_k_centers: int = Field(5, ge=1, le=20, description="Nombre de centres de santé à retourner")
    max_distance_km: float = Field(20.0, ge=1, le=200, description="Rayon de recherche en km")
    min_similarity: float = Field(0.25, ge=0.0, le=1.0, description="Similarité minimale (0-1)")

    @field_validator("sex")
    @classmethod
    def validate_sex(cls, v):
        if v is not None and v.upper() not in ("M", "F"):
            raise ValueError("sex doit être 'M' ou 'F'")
        return v.upper() if v else v


class CentersRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    max_distance_km: float = Field(20.0, ge=1, le=200)
    limit: int = Field(10, ge=1, le=50)
    category_codes: Optional[list[str]] = Field(
        None,
        description="Filtrer par codes catégorie FINESS (ex: ['355','146'] pour CHU/CH)",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post(
    "/api/suggest",
    summary="Suggérer des pathologies à partir de symptômes",
    tags=["RAG"],
)
async def suggest(request: SuggestRequest):
    """
    Pipeline RAG complet :
    1. Encode les symptômes avec multilingual-e5-base
    2. Recherche les pathologies et cas similaires dans pgvector
    3. Recherche les centres de santé proches dans MongoDB (si coordonnées fournies)
    4. Génère des hypothèses diagnostiques avec Claude
    """
    try:
        result = app.state.engine.suggest(
            symptoms=request.symptoms,
            age=request.age,
            sex=request.sex,
            latitude=request.latitude,
            longitude=request.longitude,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
            max_distance=int(request.max_distance_km * 1000),
            top_k_centers=request.top_k_centers,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur suggest : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Erreur interne : {e}")


@app.post(
    "/api/centers",
    summary="Trouver les centres de santé proches",
    tags=["Géospatial"],
)
async def find_centers(request: CentersRequest):
    """Recherche géospatiale $near sur MongoDB — centres de santé FINESS."""
    try:
        centers = app.state.mongo.search_nearby(
            longitude=request.longitude,
            latitude=request.latitude,
            max_distance=int(request.max_distance_km * 1000),
            limit=request.limit,
            category_codes=request.category_codes,
        )
        return {"centers": centers, "count": len(centers)}
    except Exception as e:
        logger.error(f"Erreur centers : {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/pathologies",
    summary="Lister les pathologies indexées",
    tags=["Données"],
)
async def list_pathologies():
    """Retourne les 49 pathologies DDXPlus indexées dans PostgreSQL."""
    try:
        pathologies = app.state.pg.get_all_pathologies()
        return {"pathologies": pathologies, "count": len(pathologies)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/health",
    summary="État de l'API",
    tags=["Monitoring"],
)
async def health():
    """Vérifie la connectivité aux bases de données et retourne les statistiques."""
    status = {"status": "ok", "databases": {}}
    try:
        pg_stats = app.state.pg.get_stats()
        status["databases"]["postgresql"] = {"status": "ok", **pg_stats}
    except Exception as e:
        status["databases"]["postgresql"] = {"status": "error", "detail": str(e)}
        status["status"] = "degraded"
    try:
        mongo_stats = app.state.mongo.get_stats()
        status["databases"]["mongodb"] = {"status": "ok", **mongo_stats}
    except Exception as e:
        status["databases"]["mongodb"] = {"status": "error", "detail": str(e)}
        status["status"] = "degraded"
    return status


@app.get("/", tags=["Info"])
async def root():
    return {
        "name": "MedRAG API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
        "description": "Outil IA d'aide à la décision clinique — Projet M2 Data Science",
    }


# ---------------------------------------------------------------------------
# Point d'entrée (développement)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("rag_engine.api:app", host=API_HOST, port=API_PORT, reload=True)
