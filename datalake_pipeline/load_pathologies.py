#!/usr/bin/env python3
"""
Phase E (1/3) — Charge les 49 pathologies DDXPlus dans PostgreSQL.
Lance : python load_pathologies.py
"""

import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

# ── Config ────────────────────────────────────────────────────────────────────

load_dotenv(Path(__file__).parent / ".env")

JSONL   = Path(__file__).parent / "processed" / "ddxplus_pathology_documents.jsonl"
PG_DSN  = os.getenv("PG_DSN", "postgresql://medrag:medrag_2024@localhost:5433/medrag")
MODEL   = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")

# ── Requête INSERT (upsert : réexécutable sans doublon) ───────────────────────

SQL = """
INSERT INTO pathology_documents
    (id, source, source_enrichment, pathology_fr, pathology_en, icd10, icd11_code,
     severity, text, description_narrative, typical_symptoms, atypical_symptoms,
     risk_factors, red_flags, embedding)
VALUES
    (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET
    embedding = EXCLUDED.embedding,
    text      = EXCLUDED.text;
"""

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    # Charger le modèle d'embedding
    print("Chargement du modèle d'embedding…")
    model = SentenceTransformer(MODEL)

    # Lire le fichier JSONL
    docs = [json.loads(line) for line in JSONL.read_text(encoding="utf-8").splitlines()]
    print(f"{len(docs)} pathologies à charger")

    # Connexion PostgreSQL
    with psycopg.connect(PG_DSN) as conn:
        register_vector(conn)

        for i, doc in enumerate(docs, 1):
            # Calculer l'embedding (préfixe "passage:" requis par e5)
            embedding = model.encode("passage: " + doc["text"]).tolist()

            conn.execute(SQL, (
                doc["id"],
                doc["source"],
                doc.get("source_enrichment"),
                doc["pathology_fr"],
                doc.get("pathology_en"),
                doc.get("icd10"),
                doc.get("icd11_code"),
                doc.get("severity"),
                doc["text"],
                doc.get("description_narrative"),
                doc.get("typical_symptoms"),
                doc.get("atypical_symptoms"),
                doc.get("risk_factors"),
                doc.get("red_flags"),
                embedding,
            ))
            print(f"  [{i:02d}/49] {doc['pathology_fr']}")

        conn.commit()

    print(f"\nTerminé — {len(docs)} pathologies chargées dans PostgreSQL.")


if __name__ == "__main__":
    main()
