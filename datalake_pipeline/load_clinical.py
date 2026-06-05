#!/usr/bin/env python3
"""
Phase E (3/3) — Charge les ~4 966 cas cliniques mtsamples dans PostgreSQL.
Lance : python load_clinical.py
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

JSONL   = Path(__file__).parent / "processed" / "mtsamples_clinical_cases.jsonl"
PG_DSN  = os.getenv("PG_DSN", "postgresql://medrag:medrag_2024@localhost:5433/medrag")
MODEL   = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")
BATCH   = int(os.getenv("EMBEDDING_BATCH", "64"))

SQL = """
INSERT INTO clinical_cases
    (id, source, medical_specialty, chief_complaint, assessment, text, embedding)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET embedding = EXCLUDED.embedding;
"""

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Chargement du modèle d'embedding…")
    model = SentenceTransformer(MODEL)

    docs = [json.loads(line) for line in JSONL.read_text(encoding="utf-8").splitlines()]
    print(f"{len(docs)} cas cliniques à charger")

    texts = ["passage: " + doc["text"] for doc in docs]
    print("Calcul des embeddings (peut prendre 3-5 min)…")
    embeddings = model.encode(texts, batch_size=BATCH, show_progress_bar=True)

    with psycopg.connect(PG_DSN) as conn:
        register_vector(conn)

        for i, (doc, emb) in enumerate(zip(docs, embeddings), 1):
            conn.execute(SQL, (
                doc["doc_id"],
                "mtsamples",
                doc.get("specialty"),
                doc.get("description"),
                doc.get("assessment"),
                doc["text"],
                emb.tolist(),
            ))
            if i % 500 == 0:
                print(f"  {i}/{len(docs)} insérés…")

        conn.commit()

    print(f"\nTerminé — {len(docs)} cas cliniques chargés dans PostgreSQL.")


if __name__ == "__main__":
    main()
