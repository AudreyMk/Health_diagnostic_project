"""
Retriever pgvector (psycopg3) + MongoDB — MedRAG v2

Trois pools de recherche PostgreSQL :
  - search_pathologies()      : descriptions de pathologies enrichies
  - search_similar_patients() : cas patients filtrés par âge/sexe
  - search_clinical_cases()   : transcriptions cliniques réelles (mtsamples)

Un pool MongoDB :
  - search_nearby()           : centres de santé FINESS ($near géospatial)
"""
import logging
from typing import Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from pgvector.psycopg import register_vector
from pymongo import MongoClient

from .config import (
    PG_DSN, PG_POOL_MIN, PG_POOL_MAX,
    MONGO_URI, MONGO_DB, MONGO_COLL,
    TOP_K, TOP_K_CENTERS, MAX_DISTANCE_METERS, MIN_SIMILARITY,
)

logger = logging.getLogger(__name__)


def _configure_connection(conn: psycopg.Connection) -> None:
    """Appelé à chaque nouvelle connexion du pool : active pgvector."""
    register_vector(conn)


class PGRetriever:
    """
    Recherche sémantique dans PostgreSQL via pgvector (psycopg3).
    Pool de connexions géré par psycopg_pool.ConnectionPool.
    Trois fonctions SQL dédiées : un pool par type de document.
    """

    def __init__(self):
        self._pool = ConnectionPool(
            conninfo=PG_DSN,
            min_size=PG_POOL_MIN,
            max_size=PG_POOL_MAX,
            configure=_configure_connection,
            kwargs={"row_factory": dict_row},
        )
        logger.info(f"Pool PostgreSQL (psycopg3) initialisé (min={PG_POOL_MIN}, max={PG_POOL_MAX})")

    # ------------------------------------------------------------------
    # Pool 1 — Pathologies enrichies
    # ------------------------------------------------------------------

    def search_pathologies(
        self,
        embedding: list[float],
        top_k: int = TOP_K,
        min_similarity: float = MIN_SIMILARITY,
    ) -> list[dict]:
        """Retourne les pathologies les plus proches sémantiquement."""
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM search_pathologies(%s::vector, %s, %s)",
                    (embedding, top_k, min_similarity),
                )
                return cur.fetchall()

    # ------------------------------------------------------------------
    # Pool 2 — Patients filtrés démographiquement
    # ------------------------------------------------------------------

    def search_similar_patients(
        self,
        embedding: list[float],
        top_k: int = TOP_K,
        min_similarity: float = 0.20,
        age: Optional[int] = None,
        sex: Optional[str] = None,
        age_range: int = 15,
    ) -> list[dict]:
        """
        Retourne des cas patients similaires.
        Filtre optionnel : âge ± age_range et/ou sexe.
        """
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM search_similar_patients(%s::vector, %s, %s, %s, %s, %s)",
                    (embedding, top_k, min_similarity, age, sex, age_range),
                )
                return cur.fetchall()

    # ------------------------------------------------------------------
    # Pool 3 — Cas cliniques réels (mtsamples)
    # ------------------------------------------------------------------

    def search_clinical_cases(
        self,
        embedding: list[float],
        top_k: int = 3,
        min_similarity: float = MIN_SIMILARITY,
    ) -> list[dict]:
        """Retourne des transcriptions cliniques réelles similaires."""
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM search_clinical_cases(%s::vector, %s, %s)",
                    (embedding, top_k, min_similarity),
                )
                return cur.fetchall()

    # ------------------------------------------------------------------
    # Utilitaires
    # ------------------------------------------------------------------

    def get_all_pathologies(self) -> list[dict]:
        """Liste toutes les pathologies indexées (endpoint /pathologies)."""
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, pathology_fr, pathology_en, icd10, icd11_code,
                           severity, red_flags
                    FROM pathology_documents
                    ORDER BY pathology_fr
                    """
                )
                return cur.fetchall()

    def get_stats(self) -> dict:
        """Statistiques pour /health."""
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM pathology_documents)                               AS pathologies,
                        (SELECT COUNT(*) FROM pathology_documents WHERE embedding IS NOT NULL)   AS pathologies_vectorisees,
                        (SELECT COUNT(*) FROM patient_descriptions)                              AS patients,
                        (SELECT COUNT(*) FROM patient_descriptions  WHERE embedding IS NOT NULL) AS patients_vectorises,
                        (SELECT COUNT(*) FROM clinical_cases)                                    AS clinical_cases,
                        (SELECT COUNT(*) FROM clinical_cases        WHERE embedding IS NOT NULL) AS clinical_cases_vectorises
                    """
                )
                row = cur.fetchone()
                return dict(row) if row else {}

    def close(self) -> None:
        self._pool.close()


class MongoRetriever:
    """Recherche géospatiale $near sur les centres de santé FINESS."""

    PRIORITY_CATEGORIES = ["355", "146", "101", "124", "129", "131", "141"]

    def __init__(self):
        self.client = MongoClient(MONGO_URI)
        self.db = self.client[MONGO_DB]
        self.coll = self.db[MONGO_COLL]
        logger.info("Connexion MongoDB initialisée")

    def search_nearby(
        self,
        longitude: float,
        latitude: float,
        max_distance: int = MAX_DISTANCE_METERS,
        limit: int = TOP_K_CENTERS,
        category_codes: Optional[list[str]] = None,
    ) -> list[dict]:
        query: dict = {
            "location": {
                "$near": {
                    "$geometry": {"type": "Point", "coordinates": [longitude, latitude]},
                    "$maxDistance": max_distance,
                }
            }
        }
        if category_codes:
            query["category_code"] = {"$in": category_codes}

        results = []
        for doc in self.coll.find(query).limit(limit):
            doc.pop("_id", None)
            results.append(doc)
        return results

    def get_stats(self) -> dict:
        return {"health_centers": self.coll.count_documents({})}

    def close(self) -> None:
        self.client.close()
