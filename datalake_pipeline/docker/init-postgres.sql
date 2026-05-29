-- ==========================================================================
-- init-postgres.sql
-- Initialisation de la base PostgreSQL pour le projet RAG Medical
-- Execute automatiquement au premier demarrage du container
-- ==========================================================================

-- Activer l'extension pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- ==========================================================================
-- Table : pathology_documents
-- Documents de pathologies vectorises pour le retrieval RAG
-- 1 ligne = 1 pathologie (49 lignes attendues depuis DDXPlus)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS pathology_documents (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL DEFAULT 'ddxplus',
    pathology_fr    TEXT NOT NULL,
    pathology_en    TEXT,
    icd10           TEXT,
    severity        INTEGER,
    text            TEXT NOT NULL,
    embedding       vector(768),  -- dimension a ajuster selon le modele
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Index HNSW pour la recherche de similarite cosinus
-- (sera cree apres insertion des embeddings car HNSW est plus rapide a construire sur des donnees existantes)
-- CREATE INDEX idx_pathology_embedding ON pathology_documents USING hnsw (embedding vector_cosine_ops);

-- ==========================================================================
-- Table : patient_descriptions
-- Descriptions textuelles de patients vectorisees pour le retrieval RAG
-- Utilise pour enrichir le contexte du LLM avec des cas similaires
-- ==========================================================================
CREATE TABLE IF NOT EXISTS patient_descriptions (
    id                      TEXT PRIMARY KEY,
    source                  TEXT NOT NULL DEFAULT 'ddxplus',
    pathology_fr            TEXT NOT NULL,
    age                     INTEGER,
    sex                     CHAR(1),
    text                    TEXT NOT NULL,
    differential_diagnosis  TEXT,
    embedding               vector(768),
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================================================
-- Table : csv_symptom_descriptions
-- Descriptions de symptomes du CSV (anglais, 27 pathologies)
-- Utilise pour evaluation et comme complement au retrieval
-- ==========================================================================
CREATE TABLE IF NOT EXISTS csv_symptom_descriptions (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL DEFAULT 'csv_symptoms',
    pathology_en    TEXT NOT NULL,
    language        TEXT DEFAULT 'en',
    text            TEXT NOT NULL,
    embedding       vector(768),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================================================
-- Vue : recherche unifiee sur tous les documents
-- Permet au RAGEngine de chercher dans toutes les tables a la fois
-- ==========================================================================
CREATE OR REPLACE VIEW all_documents AS
    SELECT id, source, pathology_fr AS pathology, text, embedding, created_at
    FROM pathology_documents
    WHERE embedding IS NOT NULL
  UNION ALL
    SELECT id, source, pathology_fr AS pathology, text, embedding, created_at
    FROM patient_descriptions
    WHERE embedding IS NOT NULL;

-- ==========================================================================
-- Fonction : recherche par similarite cosinus
-- Utilisee par le RAGEngine pour le retrieval
-- ==========================================================================
CREATE OR REPLACE FUNCTION search_similar_documents(
    query_embedding vector(768),
    match_count     INTEGER DEFAULT 5,
    min_similarity  FLOAT DEFAULT 0.3
)
RETURNS TABLE (
    id          TEXT,
    source      TEXT,
    pathology   TEXT,
    text        TEXT,
    similarity  FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.source,
        d.pathology,
        d.text,
        1 - (d.embedding <=> query_embedding) AS similarity
    FROM all_documents d
    WHERE 1 - (d.embedding <=> query_embedding) >= min_similarity
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ==========================================================================
-- Table : query_logs (optionnel, pour le suivi des requetes)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS query_logs (
    id              SERIAL PRIMARY KEY,
    query_text      TEXT NOT NULL,
    patient_age     INTEGER,
    patient_sex     CHAR(1),
    results         JSONB,
    response_time   FLOAT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Message de confirmation
DO $$
BEGIN
    RAISE NOTICE '=== PostgreSQL medrag initialise avec succes ===';
    RAISE NOTICE 'Extension pgvector : activee';
    RAISE NOTICE 'Tables : pathology_documents, patient_descriptions, csv_symptom_descriptions';
    RAISE NOTICE 'Fonction : search_similar_documents()';
END
$$;
