
#!/usr/bin/env python3
"""
Phase E (2/3) — Charge les 2 450 patients DDXPlus dans PostgreSQL.
Lance : python load_patients.py
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

JSONL   = Path(__file__).parent / "processed" / "ddxplus_patient_descriptions.jsonl"
PG_DSN  = os.getenv("PG_DSN", "postgresql://medrag:medrag_2024@localhost:5433/medrag")
MODEL   = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-base")
BATCH   = int(os.getenv("EMBEDDING_BATCH", "64"))

SQL = """
INSERT INTO patient_descriptions
    (id, source, pathology_fr, age, sex, age_group, text, differential_diagnosis, embedding)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (id) DO UPDATE SET embedding = EXCLUDED.embedding;
"""

# ── Utilitaire ────────────────────────────────────────────────────────────────

def format_diff_diag(dd_list: list) -> str:
    """Convertit la liste en texte : 'Pneumonie (78%) ; Bronchite (12%)'"""
    parts = [f"{d['pathology_fr']} ({round(d['probability']*100)}%)" for d in dd_list]
    return " ; ".join(parts)

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("Chargement du modèle d'embedding…")
    model = SentenceTransformer(MODEL)

    docs = [json.loads(line) for line in JSONL.read_text(encoding="utf-8").splitlines()]
    print(f"{len(docs)} patients à charger")

    # Calculer tous les embeddings en batch (plus rapide qu'un par un)
    texts = ["passage: " + doc["text"] for doc in docs]
    print("Calcul des embeddings (peut prendre 1-2 min)…")
    embeddings = model.encode(texts, batch_size=BATCH, show_progress_bar=True)

    # Insérer dans PostgreSQL
    with psycopg.connect(PG_DSN) as conn:
        register_vector(conn)

        for i, (doc, emb) in enumerate(zip(docs, embeddings), 1):
            conn.execute(SQL, (
                doc["doc_id"],
                "ddxplus",
                doc["pathology_fr"],
                doc["age"],
                doc["sex"],
                doc["age_group"],
                doc["text"],
                format_diff_diag(doc.get("differential_diagnosis", [])),
                emb.tolist(),
            ))
            if i % 250 == 0:
                print(f"  {i}/{len(docs)} insérés…")

        conn.commit()

    print(f"\nTerminé — {len(docs)} patients chargés dans PostgreSQL.")


if __name__ == "__main__":
    main()
