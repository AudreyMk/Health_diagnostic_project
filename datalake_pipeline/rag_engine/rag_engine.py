"""
MedRAGEngine v2 — Orchestrateur du pipeline RAG médical.

Pipeline :
  1. Encoder la requête (symptômes) avec multilingual-e5-base
  2. Retrieval Pool 1 → pathologies enrichies (ICD-11 + Wikipedia)
  3. Retrieval Pool 2 → patients similaires filtrés par âge/sexe
  4. Retrieval Pool 3 → cas cliniques réels (mtsamples)
  5. Retrieval MongoDB → centres de santé proches (si coordonnées)
  6. Appel Claude avec contexte structuré par pool
  7. Retourner la réponse structurée
"""
import time
import logging
from typing import Optional

from .embedding_manager import EmbeddingManager
from .retriever import PGRetriever, MongoRetriever
from .llm_client import LLMClient
from .config import (
    TOP_K_PATHOLOGIES, TOP_K_PATIENTS, TOP_K_CLINICAL,
    TOP_K_CENTERS, MAX_DISTANCE_METERS, MIN_SIMILARITY, AGE_RANGE,
)

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
        top_k_pathologies: int = TOP_K_PATHOLOGIES,
        top_k_patients: int = TOP_K_PATIENTS,
        top_k_clinical: int = TOP_K_CLINICAL,
        min_similarity: float = MIN_SIMILARITY,
        max_distance: int = MAX_DISTANCE_METERS,
        top_k_centers: int = TOP_K_CENTERS,
        age_range: int = AGE_RANGE,
    ) -> dict:
        start = time.time()

        # 1. Encoder la requête
        t0 = time.time()
        embedding = self.embedder.encode_query(symptoms)
        embed_time = round(time.time() - t0, 3)

        # 2. Pool 1 — Pathologies enrichies
        t0 = time.time()
        patho_docs = self.pg.search_pathologies(
            embedding, top_k=top_k_pathologies, min_similarity=min_similarity
        )
        pg_patho_time = round(time.time() - t0, 3)
        logger.info(f"Pool 1 — {len(patho_docs)} pathologies ({pg_patho_time}s)")

        # 3. Pool 2 — Patients similaires (filtrés par âge/sexe si fournis)
        t0 = time.time()
        patient_docs = self.pg.search_similar_patients(
            embedding,
            top_k=top_k_patients,
            min_similarity=0.20,
            age=age,
            sex=sex,
            age_range=age_range,
        )
        pg_patients_time = round(time.time() - t0, 3)
        logger.info(
            f"Pool 2 — {len(patient_docs)} patients "
            f"(filtre: âge={age}±{age_range}, sexe={sex}) ({pg_patients_time}s)"
        )

        # 4. Pool 3 — Cas cliniques réels
        t0 = time.time()
        clinical_docs = self.pg.search_clinical_cases(
            embedding, top_k=top_k_clinical, min_similarity=min_similarity
        )
        pg_clinical_time = round(time.time() - t0, 3)
        logger.info(f"Pool 3 — {len(clinical_docs)} cas cliniques ({pg_clinical_time}s)")

        # 5. Centres de santé proches (si coordonnées fournies)
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
            logger.info(f"MongoDB — {len(nearby_centers)} centres ({mongo_time}s)")

        # 6. Génération LLM avec contexte structuré
        t0 = time.time()
        llm_response, llm_usage = self.llm.suggest(
            symptoms=symptoms,
            patho_docs=patho_docs,
            patient_docs=patient_docs,
            clinical_docs=clinical_docs,
            age=age,
            sex=sex,
        )
        llm_time = round(time.time() - t0, 3)

        total_time = round(time.time() - start, 2)

        top_similarity = patho_docs[0]["similarity"] if patho_docs else 0.0

        return {
            "query": symptoms,
            "patient_info": {"age": age, "sex": sex},
            "pathologies_retrieved": patho_docs,
            "similar_patients": patient_docs,
            "clinical_cases": clinical_docs,
            "nearby_centers": nearby_centers,
            "llm_response": llm_response,
            "llm_usage": llm_usage,
            "performance": {
                "embed_seconds": embed_time,
                "pg_pathologies_seconds": pg_patho_time,
                "pg_patients_seconds": pg_patients_time,
                "pg_clinical_seconds": pg_clinical_time,
                "mongo_seconds": mongo_time,
                "llm_seconds": llm_time,
                "total_seconds": total_time,
            },
            "retrieval_stats": {
                "pathologies_found": len(patho_docs),
                "patients_found": len(patient_docs),
                "clinical_cases_found": len(clinical_docs),
                "centers_found": len(nearby_centers),
                "top_similarity": top_similarity,
            },
        }

    def close(self):
        self.pg.close()
        self.mongo.close()
