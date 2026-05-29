"""
MedRAGEngine — Orchestrateur principal du pipeline RAG médical.

Pipeline :
  1. Encoder la requête (symptômes) avec multilingual-e5-base
  2. Retrieval pgvector → pathologies + cas patients similaires
  3. Retrieval MongoDB → centres de santé proches (optionnel)
  4. Appel Claude avec le contexte récupéré
  5. Retourner la réponse structurée
"""
import time
import logging
from typing import Optional

from .embedding_manager import EmbeddingManager
from .retriever import PGRetriever, MongoRetriever
from .llm_client import LLMClient
from .config import TOP_K, TOP_K_CENTERS, MAX_DISTANCE_METERS, MIN_SIMILARITY

logger = logging.getLogger(__name__)


class MedRAGEngine:
    def __init__(
        self,
        embedder: EmbeddingManager,
        pg: PGRetriever,
        mongo: MongoRetriever,
        llm: LLMClient,
    ):
        self.embedder = embedder
        self.pg = pg
        self.mongo = mongo
        self.llm = llm

    def suggest(
        self,
        symptoms: str,
        age: Optional[int] = None,
        sex: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        top_k: int = TOP_K,
        min_similarity: float = MIN_SIMILARITY,
        max_distance: int = MAX_DISTANCE_METERS,
        top_k_centers: int = TOP_K_CENTERS,
    ) -> dict:
        start = time.time()

        # 1. Encoder la requête
        t0 = time.time()
        embedding = self.embedder.encode_query(symptoms)
        embed_time = round(time.time() - t0, 3)

        # 2. Retrieval pgvector
        t0 = time.time()
        retrieved = self.pg.search(embedding, top_k=top_k, min_similarity=min_similarity)
        pg_time = round(time.time() - t0, 3)

        patho_docs = [d for d in retrieved if "patho_" in d.get("id", "")]
        patient_docs = [d for d in retrieved if "patient_" in d.get("id", "")]

        logger.info(
            f"Retrieval PG : {len(patho_docs)} pathologies, "
            f"{len(patient_docs)} patients similaires ({pg_time}s)"
        )

        # 3. Centres de santé proches (si coordonnées fournies)
        nearby_centers: list[dict] = []
        mongo_time = 0.0
        if latitude is not None and longitude is not None:
            t0 = time.time()
            nearby_centers = self.mongo.search_nearby(
                longitude=longitude,
                latitude=latitude,
                max_distance=max_distance,
                limit=top_k_centers,
            )
            mongo_time = round(time.time() - t0, 3)
            logger.info(f"Retrieval MongoDB : {len(nearby_centers)} centres ({mongo_time}s)")

        # 4. Génération LLM
        t0 = time.time()
        llm_response, llm_usage = self.llm.suggest(
            symptoms=symptoms,
            retrieved_docs=retrieved,
            age=age,
            sex=sex,
        )
        llm_time = round(time.time() - t0, 3)

        total_time = round(time.time() - start, 2)

        return {
            "query": symptoms,
            "patient_info": {"age": age, "sex": sex},
            "pathologies_retrieved": patho_docs,
            "similar_patients": patient_docs,
            "nearby_centers": nearby_centers,
            "llm_response": llm_response,
            "llm_usage": llm_usage,
            "performance": {
                "embed_seconds": embed_time,
                "pg_seconds": pg_time,
                "mongo_seconds": mongo_time,
                "llm_seconds": llm_time,
                "total_seconds": total_time,
            },
            "retrieval_stats": {
                "pathologies_found": len(patho_docs),
                "patients_found": len(patient_docs),
                "centers_found": len(nearby_centers),
                "top_similarity": patho_docs[0]["similarity"] if patho_docs else 0.0,
            },
        }

    def close(self):
        self.pg.close()
        self.mongo.close()
