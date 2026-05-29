"""
=============================================================================
Script d'import des donnees traitees vers PostgreSQL et MongoDB
Projet M2 - RAG Medical
=============================================================================

Etapes :
  1. MongoDB  <- finess_health_centers.jsonl      (17 235 centres)
  2. PostgreSQL <- ddxplus_pathology_documents.jsonl  (49 pathologies)
  3. PostgreSQL <- ddxplus_patient_descriptions.jsonl (100 000 patients)
  4. PostgreSQL <- csv_symptom_descriptions.jsonl     (1 606 descriptions)
  5. Vectorisation des textes avec sentence-transformers -> embeddings pgvector

Usage :
  python load_to_databases.py                  # Tout importer
  python load_to_databases.py --skip-embed     # Importer sans vectoriser
  python load_to_databases.py --only mongodb   # Seulement MongoDB
  python load_to_databases.py --only postgres  # Seulement PostgreSQL
  python load_to_databases.py --only embed     # Seulement la vectorisation

Prerequis :
  pip install pymongo psycopg2-binary sentence-transformers tqdm python-dotenv
"""

import os
import json
import time
import argparse
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras
from pymongo import MongoClient, InsertOne
from pymongo.errors import BulkWriteError
from tqdm import tqdm
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROCESSED_DIR = Path(__file__).parent / "processed"

PG_DSN = os.getenv(
    "PG_DSN",
    "postgresql://medrag:medrag_2024@localhost:5432/medrag"
)
MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://medrag:medrag_2024@localhost:27017/"
)
MONGO_DB   = "medrag"
MONGO_COLL = "health_centers"

# Modele d'embedding : camembert ou multilingual
# camembert-base     -> 768 dims, francais uniquement
# multilingual-e5-base -> 768 dims, multilingue (recommande pour ce projet)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")
EMBEDDING_BATCH = int(os.getenv("EMBEDDING_BATCH", "64"))
# Lots DB plus petits = commits plus frequents, moins de risque si la connexion coupe
DB_WRITE_BATCH = int(os.getenv("DB_WRITE_BATCH", "32"))
EMBED_RECONNECT_EVERY = int(os.getenv("EMBED_RECONNECT_EVERY", "25"))  # nouvelle connexion tous les N lots

MONGO_BATCH_SIZE = 500
PG_BATCH_SIZE    = 500


# ---------------------------------------------------------------------------
# 1. Import MongoDB - FINESS health centers
# ---------------------------------------------------------------------------

class MongoImporter:
    """Importe les centres de sante FINESS dans MongoDB."""

    def __init__(self, uri: str, db_name: str, collection: str):
        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.coll = self.db[collection]

    def import_health_centers(self, jsonl_path: Path) -> dict:
        logger.info("=" * 60)
        logger.info("[1/4] Import MongoDB - Centres de sante FINESS")
        logger.info("=" * 60)

        # Vider la collection (sauf le doc init)
        self.coll.delete_many({"source": "finess"})
        self.coll.delete_many({"_id": "init_check"})

        docs = []
        total = 0
        inserted = 0
        errors = 0

        with open(jsonl_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        logger.info(f"  Fichier : {jsonl_path.name} ({len(lines)} lignes)")

        for line in tqdm(lines, desc="  Import FINESS", unit="doc"):
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
                # Utiliser l'id comme _id MongoDB
                doc["_id"] = doc.get("id", doc.get("finess_id"))
                docs.append(InsertOne(doc))
                total += 1

                if len(docs) >= MONGO_BATCH_SIZE:
                    result = self._bulk_insert(docs)
                    inserted += result["inserted"]
                    errors   += result["errors"]
                    docs = []

            except json.JSONDecodeError as e:
                logger.warning(f"  JSON invalide : {e}")

        # Dernier batch
        if docs:
            result = self._bulk_insert(docs)
            inserted += result["inserted"]
            errors   += result["errors"]

        stats = {
            "total_read": total,
            "inserted": inserted,
            "errors": errors,
            "collection": f"{MONGO_DB}.{MONGO_COLL}",
        }
        logger.info(f"  -> {inserted}/{total} documents importes ({errors} erreurs)")

        # Verifier les index
        indexes = list(self.coll.index_information().keys())
        logger.info(f"  Index actifs : {', '.join(indexes)}")

        return stats

    def _bulk_insert(self, ops: list) -> dict:
        try:
            result = self.coll.bulk_write(ops, ordered=False)
            return {"inserted": result.inserted_count, "errors": 0}
        except BulkWriteError as e:
            ok = e.details.get("nInserted", 0)
            err = len(e.details.get("writeErrors", []))
            return {"inserted": ok, "errors": err}

    def close(self):
        self.client.close()


# ---------------------------------------------------------------------------
# 2. Import PostgreSQL - Documents textuels (sans embeddings)
# ---------------------------------------------------------------------------

class PostgresImporter:
    """Importe les documents DDXPlus et CSV dans PostgreSQL."""

    def __init__(self, dsn: str):
        self.conn = psycopg2.connect(dsn)
        self.conn.autocommit = False

    def import_pathology_documents(self, jsonl_path: Path) -> dict:
        logger.info("=" * 60)
        logger.info("[2/4] Import PostgreSQL - Pathology documents")
        logger.info("=" * 60)
        return self._import_jsonl(
            jsonl_path=jsonl_path,
            table="pathology_documents",
            columns=["id", "source", "pathology_fr", "pathology_en",
                     "icd10", "severity", "text"],
            row_mapper=self._map_pathology_doc,
        )

    def import_patient_descriptions(self, jsonl_path: Path) -> dict:
        logger.info("=" * 60)
        logger.info("[3/4] Import PostgreSQL - Patient descriptions")
        logger.info("=" * 60)
        return self._import_jsonl(
            jsonl_path=jsonl_path,
            table="patient_descriptions",
            columns=["id", "source", "pathology_fr", "age", "sex",
                     "text", "differential_diagnosis"],
            row_mapper=self._map_patient_doc,
        )

    def import_csv_symptoms(self, jsonl_path: Path) -> dict:
        logger.info("=" * 60)
        logger.info("[4/4] Import PostgreSQL - CSV symptom descriptions")
        logger.info("=" * 60)
        return self._import_jsonl(
            jsonl_path=jsonl_path,
            table="csv_symptom_descriptions",
            columns=["id", "source", "pathology_en", "language", "text"],
            row_mapper=self._map_csv_doc,
        )

    def _import_jsonl(self, jsonl_path: Path, table: str,
                      columns: list, row_mapper) -> dict:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        logger.info(f"  Fichier : {jsonl_path.name} ({len(lines)} lignes)")

        # Vider la table avant import
        with self.conn.cursor() as cur:
            cur.execute(f"TRUNCATE TABLE {table} CASCADE")
        self.conn.commit()

        batch = []
        total = inserted = errors = 0
        placeholders = ",".join(["%s"] * len(columns))
        sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders}) ON CONFLICT (id) DO NOTHING"

        for line in tqdm(lines, desc=f"  Import {table}", unit="doc"):
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
                row = row_mapper(doc)
                if row:
                    batch.append(row)
                    total += 1

                if len(batch) >= PG_BATCH_SIZE:
                    n = self._execute_batch(sql, batch)
                    inserted += n
                    errors += len(batch) - n
                    batch = []

            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"  Ligne ignoree : {e}")

        if batch:
            n = self._execute_batch(sql, batch)
            inserted += n
            errors += len(batch) - n

        self.conn.commit()
        stats = {"table": table, "total_read": total,
                 "inserted": inserted, "errors": errors}
        logger.info(f"  -> {inserted}/{total} lignes inserees ({errors} erreurs)")
        return stats

    def _execute_batch(self, sql: str, batch: list) -> int:
        try:
            with self.conn.cursor() as cur:
                psycopg2.extras.execute_batch(cur, sql, batch, page_size=PG_BATCH_SIZE)
            self.conn.commit()
            return len(batch)
        except Exception as e:
            self.conn.rollback()
            logger.error(f"  Erreur batch : {e}")
            return 0

    @staticmethod
    def _map_pathology_doc(doc: dict) -> Optional[tuple]:
        return (
            doc["id"],
            doc.get("source", "ddxplus"),
            doc.get("pathology_fr", ""),
            doc.get("pathology_en"),
            doc.get("icd10"),
            doc.get("severity"),
            doc.get("text", ""),
        )

    @staticmethod
    def _map_patient_doc(doc: dict) -> Optional[tuple]:
        return (
            doc["id"],
            doc.get("source", "ddxplus"),
            doc.get("pathology_fr", ""),
            doc.get("age"),
            doc.get("sex"),
            doc.get("text", ""),
            doc.get("differential_diagnosis"),
        )

    @staticmethod
    def _map_csv_doc(doc: dict) -> Optional[tuple]:
        return (
            doc["id"],
            doc.get("source", "csv_symptoms"),
            doc.get("pathology_en", ""),
            doc.get("language", "en"),
            doc.get("text", ""),
        )

    def close(self):
        self.conn.close()


def _dsn_target_label(dsn: str) -> str:
    """Affiche hote + base sans mot de passe (pour les logs)."""
    try:
        p = urlparse(dsn)
        host = p.hostname or "?"
        db = (p.path or "").lstrip("/") or "postgres"
        return f"{host}:{p.port or 5432}/{db}"
    except Exception:
        return "(dsn)"


# ---------------------------------------------------------------------------
# 3. Vectorisation + mise a jour des embeddings dans PostgreSQL
# ---------------------------------------------------------------------------

class EmbeddingLoader:
    """
    Vectorise les textes et met a jour la colonne embedding dans PostgreSQL.
    Modele : multilingual-e5-base (768 dims, supporte FR + EN)
    Connexion courte par lot + reconnexion periodique pour eviter les coupures longues.
    """

    def __init__(self, dsn: str, model_name: str = EMBEDDING_MODEL):
        logger.info(f"  Chargement du modele : {model_name}")
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        self.dsn = dsn
        self._conn = None
        logger.info("  Modele charge.")

    def _connect(self):
        """Nouvelle connexion avec keepalives TCP et sans timeout SQL."""
        if self._conn and not self._conn.closed:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = psycopg2.connect(
            self.dsn,
            connect_timeout=60,
            keepalives=1,
            keepalives_idle=30,
            keepalives_interval=10,
            keepalives_count=5,
        )
        self._conn.autocommit = False
        with self._conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            cur.execute("SET idle_in_transaction_session_timeout = 0")
        self._conn.commit()

    def _safe_close(self):
        if self._conn and not self._conn.closed:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None

    def vectorize_table(self, table: str, text_col: str = "text",
                        prefix: str = "passage: ") -> dict:
        """
        Vectorise tous les textes d'une table et stocke les embeddings.
        Reprend automatiquement sur les lignes ou embedding IS NULL.
        """
        logger.info(f"  Vectorisation de {table}...")

        self._connect()
        try:
            with self._conn.cursor() as cur:
                cur.execute(f"SELECT id, {text_col} FROM {table} WHERE embedding IS NULL")
                rows = cur.fetchall()
        finally:
            self._safe_close()

        if not rows:
            # Diagnostic : evite la confusion "0 vecteurs" vs mauvaise connexion
            self._connect()
            try:
                with self._conn.cursor() as cur:
                    cur.execute(
                        f"SELECT COUNT(*), COUNT(embedding), "
                        f"COUNT(*) FILTER (WHERE embedding IS NULL) FROM {table}"
                    )
                    total, avec_emb, sans_emb = cur.fetchone()
                logger.info(
                    f"  {table} : rien a vectoriser (0 ligne avec embedding NULL)."
                )
                logger.info(
                    f"  Etat sur {_dsn_target_label(self.dsn)} -> "
                    f"total={total}, avec_embedding={avec_emb}, sans_embedding={sans_emb}"
                )
            finally:
                self._safe_close()
            return {"table": table, "vectorized": 0}

        logger.info(f"  {len(rows)} documents a vectoriser dans {table}")
        updated = 0
        batch_num = 0

        for i in tqdm(range(0, len(rows), EMBEDDING_BATCH),
                      desc=f"  Embeddings {table}", unit="batch"):
            batch = rows[i:i + EMBEDDING_BATCH]
            ids   = [r[0] for r in batch]
            texts = [prefix + r[1] for r in batch]

            embeddings = self.model.encode(
                texts,
                batch_size=min(EMBEDDING_BATCH, 32),
                show_progress_bar=False,
                normalize_embeddings=True,
            )

            payload = [(emb.tolist(), rid) for emb, rid in zip(embeddings, ids)]

            for attempt in range(5):
                try:
                    if batch_num % EMBED_RECONNECT_EVERY == 0 or self._conn is None or self._conn.closed:
                        self._connect()

                    with self._conn.cursor() as cur:
                        psycopg2.extras.execute_batch(
                            cur,
                            f"UPDATE {table} SET embedding = %s::vector WHERE id = %s",
                            payload,
                            page_size=DB_WRITE_BATCH,
                        )
                    self._conn.commit()
                    updated += len(batch)
                    batch_num += 1
                    break

                except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                    logger.warning(
                        f"  Connexion PostgreSQL perdue (tentative {attempt + 1}/5): {e}"
                    )
                    self._safe_close()
                    time.sleep(min(2 ** attempt, 30))
                    if attempt == 4:
                        logger.error("  Abandon apres 5 echecs sur ce lot.")
                        raise

                except Exception as e:
                    try:
                        if self._conn and not self._conn.closed:
                            self._conn.rollback()
                    except Exception:
                        self._safe_close()
                    logger.error(f"  Erreur mise a jour embeddings : {e}")
                    raise

        self._safe_close()
        logger.info(f"  -> {updated} embeddings inseres dans {table}")
        return {"table": table, "vectorized": updated}

    def create_hnsw_index(self, table: str) -> None:
        """Cree l'index HNSW apres vectorisation pour des recherches rapides."""
        logger.info(f"  Creation index HNSW sur {table}...")
        self._connect()
        try:
            with self._conn.cursor() as cur:
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table}_embedding "
                    f"ON {table} USING hnsw (embedding vector_cosine_ops) "
                    f"WITH (m = 16, ef_construction = 64)"
                )
            self._conn.commit()
        finally:
            self._safe_close()
        logger.info(f"  Index HNSW cree sur {table}")

    def close(self):
        self._safe_close()


# ---------------------------------------------------------------------------
# Pipeline principal
# ---------------------------------------------------------------------------

class DatabaseLoader:
    """Orchestrateur principal de l'import."""

    def __init__(self, args):
        self.args = args
        self.stats = {}

    def run(self):
        only = self.args.only

        logger.info("#" * 60)
        logger.info("  IMPORT DES DONNEES -> MONGODB + POSTGRESQL")
        logger.info("#" * 60)

        # --- MongoDB ---
        if only in (None, "mongodb"):
            self._run_mongodb()

        # --- PostgreSQL (import textes) ---
        if only in (None, "postgres", "embed"):
            self._run_postgres()

        # --- Vectorisation ---
        if only in (None, "embed") and not self.args.skip_embed:
            self._run_embeddings()

        # --- Rapport final ---
        self._print_summary()

    def _run_mongodb(self):
        jsonl = PROCESSED_DIR / "finess_health_centers.jsonl"
        if not jsonl.exists():
            logger.warning(f"  Fichier absent : {jsonl}")
            return
        importer = MongoImporter(MONGO_URI, MONGO_DB, MONGO_COLL)
        try:
            self.stats["mongodb"] = importer.import_health_centers(jsonl)
        finally:
            importer.close()

    def _run_postgres(self):
        if self.args.only == "embed":
            return

        importer = PostgresImporter(PG_DSN)
        try:
            patho = PROCESSED_DIR / "ddxplus_pathology_documents.jsonl"
            if patho.exists():
                self.stats["pathology_documents"] = importer.import_pathology_documents(patho)

            patients = PROCESSED_DIR / "ddxplus_patient_descriptions.jsonl"
            if patients.exists():
                self.stats["patient_descriptions"] = importer.import_patient_descriptions(patients)

            csv_symp = PROCESSED_DIR / "csv_symptom_descriptions.jsonl"
            if csv_symp.exists():
                self.stats["csv_symptoms"] = importer.import_csv_symptoms(csv_symp)
        finally:
            importer.close()

    def _run_embeddings(self):
        logger.info("=" * 60)
        logger.info("[5/5] Vectorisation des textes (sentence-transformers)")
        logger.info("=" * 60)
        loader = EmbeddingLoader(PG_DSN, EMBEDDING_MODEL)
        try:
            self.stats["embed_pathologies"] = loader.vectorize_table(
                "pathology_documents", prefix="passage: "
            )
            self.stats["embed_patients"] = loader.vectorize_table(
                "patient_descriptions", prefix="passage: "
            )
            # Creer les index HNSW apres vectorisation
            loader.create_hnsw_index("pathology_documents")
            loader.create_hnsw_index("patient_descriptions")
        finally:
            loader.close()

    def _print_summary(self):
        logger.info("")
        logger.info("#" * 60)
        logger.info("  IMPORT TERMINE")
        logger.info("#" * 60)

        if "mongodb" in self.stats:
            s = self.stats["mongodb"]
            logger.info(f"  MongoDB  health_centers     : {s['inserted']:>7} documents")

        for key in ["pathology_documents", "patient_descriptions", "csv_symptoms"]:
            if key in self.stats:
                s = self.stats[key]
                logger.info(f"  PG       {key:<25}: {s['inserted']:>7} lignes")

        for key in ["embed_pathologies", "embed_patients"]:
            if key in self.stats:
                s = self.stats[key]
                logger.info(f"  Embed    {s['table']:<25}: {s['vectorized']:>7} vecteurs")

        logger.info("")
        logger.info("  Bases accessibles :")
        logger.info("   pgAdmin      -> http://localhost:5050")
        logger.info("   MongoExpress -> http://localhost:8081")
        logger.info("#" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(
        description="Import des donnees traitees vers MongoDB et PostgreSQL"
    )
    p.add_argument(
        "--only",
        choices=["mongodb", "postgres", "embed"],
        default=None,
        help="Executer seulement une partie (defaut: tout)",
    )
    p.add_argument(
        "--skip-embed",
        action="store_true",
        help="Importer les textes sans vectoriser (plus rapide, embeddings plus tard)",
    )
    return p.parse_args()


def main():
    args = parse_args()
    loader = DatabaseLoader(args)
    loader.run()


if __name__ == "__main__":
    main()
