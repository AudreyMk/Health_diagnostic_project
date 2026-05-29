"""
Retriever pgvector + MongoDB pour le RAG médical.

PGRetriever  : appelle search_similar_documents() définie dans init-postgres.sql
MongoRetriever : requête $near géospatiale sur la collection health_centers
"""
import logging
from typing import Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool
from pymongo import MongoClient

from .config import (
    PG_DSN, PG_POOL_MIN, PG_POOL_MAX,
    MONGO_URI, MONGO_DB, MONGO_COLL,
    TOP_K, TOP_K_CENTERS, MAX_DISTANCE_METERS, MIN_SIMILARITY,
)

logger = logging.getLogger(__name__)


class PGRetriever:
    """
    Recherche par similarité cosinus dans pgvector.
    Utilise un ThreadedConnectionPool pour supporter les requêtes concurrentes.
    """

    def __init__(self):
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            PG_POOL_MIN, PG_POOL_MAX, PG_DSN
        )
        logger.info(f"Pool PostgreSQL initialisé (min={PG_POOL_MIN}, max={PG_POOL_MAX})")

    def search(
        self,
        embedding: list[float],
        top_k: int = TOP_K,
        min_similarity: float = MIN_SIMILARITY,
    ) -> list[dict]:
        conn = self._pool.getconn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM search_similar_documents(%s::vector, %s, %s)",
                    (embedding, top_k, min_similarity),
                )
                return [dict(row) for row in cur.fetchall()]
        finally:
            self._pool.putconn(conn)

    def get_all_pathologies(self) -> list[dict]:
        """Retourne toutes les pathologies indexées (pour l'endpoint /pathologies)."""
        conn = self._pool.getconn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, pathology_fr, pathology_en, icd10, severity
                    FROM pathology_documents
                    ORDER BY pathology_fr
                    """
                )
                return [dict(row) for row in cur.fetchall()]
        finally:
            self._pool.putconn(conn)

    def get_stats(self) -> dict:
        """Retourne les statistiques de la base pour /health."""
        conn = self._pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM pathology_documents) AS pathologies,
                        (SELECT COUNT(*) FROM patient_descriptions) AS patients,
                        (SELECT COUNT(*) FROM pathology_documents WHERE embedding IS NOT NULL) AS pathologies_vectorisees,
                        (SELECT COUNT(*) FROM patient_descriptions WHERE embedding IS NOT NULL) AS patients_vectorises
                    """
                )
                row = cur.fetchone()
                return {
                    "pathologies": row[0],
                    "patients": row[1],
                    "pathologies_vectorisees": row[2],
                    "patients_vectorises": row[3],
                }
        finally:
            self._pool.putconn(conn)

    def close(self):
        self._pool.closeall()


class MongoRetriever:
    """Recherche géospatiale $near sur les centres de santé FINESS."""

    # Codes catégories prioritaires (urgences, CHU, CH, cliniques)
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
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [longitude, latitude],
                    },
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

    def close(self):
        self.client.close()
