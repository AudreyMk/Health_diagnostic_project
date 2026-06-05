-- ==========================================================================
-- init-postgres.sql — MedRAG v2
-- ==========================================================================

CREATE EXTENSION IF NOT EXISTS vector;

-- ==========================================================================
-- TABLE : pathology_documents
-- 1 ligne = 1 pathologie enrichie (ICD-11 + Wikipedia + DDXPlus)
-- `text` = champ vectorisé = description_narrative + symptômes + red_flags
-- ==========================================================================
CREATE TABLE IF NOT EXISTS pathology_documents (
    id                      TEXT PRIMARY KEY,
    source                  TEXT NOT NULL DEFAULT 'ddxplus',
    source_enrichment       TEXT,                    -- 'icd11', 'wikipedia', 'has'
    pathology_fr            TEXT NOT NULL,
    pathology_en            TEXT,
    icd10                   TEXT,
    icd11_code              TEXT,
    severity                INTEGER,                 -- 1=critique … 5=bénigne
    text                    TEXT NOT NULL,           -- champ vectorisé
    description_narrative   TEXT,                    -- paragraphe clinique complet
    typical_symptoms        TEXT,                    -- présentation typique
    atypical_symptoms       TEXT,                    -- présentation atypique
    risk_factors            TEXT,
    red_flags               TEXT,                    -- signes d'alarme → urgences
    embedding               vector(768),
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================================================
-- TABLE : patient_descriptions
-- ~2 450 lignes (50 patients/pathologie × 49, diversité démographique)
-- Sélection : 10 par combinaison (age_group × sex) par pathologie
-- ==========================================================================
CREATE TABLE IF NOT EXISTS patient_descriptions (
    id                      TEXT PRIMARY KEY,
    source                  TEXT NOT NULL DEFAULT 'ddxplus',
    pathology_fr            TEXT NOT NULL,
    age                     INTEGER,
    sex                     CHAR(1),
    age_group               TEXT,                    -- 'young'|'middle'|'senior'
    text                    TEXT NOT NULL,           -- champ vectorisé
    differential_diagnosis  TEXT,                    -- "Pneumonie 78% ; Bronchite 12%"
    embedding               vector(768),
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================================================
-- TABLE : clinical_cases
-- Transcriptions cliniques réelles (mtsamples) — ~4 999 cas
-- ==========================================================================
CREATE TABLE IF NOT EXISTS clinical_cases (
    id                      TEXT PRIMARY KEY,
    source                  TEXT NOT NULL DEFAULT 'mtsamples',
    medical_specialty       TEXT,
    chief_complaint         TEXT,
    assessment              TEXT,
    text                    TEXT NOT NULL,           -- champ vectorisé
    embedding               vector(768),
    created_at              TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================================================
-- TABLE : query_logs — traçabilité obligatoire en contexte médical
-- ==========================================================================
CREATE TABLE IF NOT EXISTS query_logs (
    id              BIGSERIAL PRIMARY KEY,
    query_text      TEXT NOT NULL,
    patient_age     INTEGER,
    patient_sex     CHAR(1),
    triage_level    INTEGER,                         -- 1=urgence vitale … 5=domicile
    results         JSONB,
    response_time   FLOAT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================================================
-- FONCTION : search_pathologies — Pool 1
-- Recherche dans les descriptions de pathologies enrichies
-- ==========================================================================
CREATE OR REPLACE FUNCTION search_pathologies(
    query_embedding vector(768),
    match_count     INTEGER DEFAULT 5,
    min_similarity  FLOAT DEFAULT 0.25
)
RETURNS TABLE (
    id                    TEXT,
    source                TEXT,
    pathology_fr          TEXT,
    text                  TEXT,
    description_narrative TEXT,
    red_flags             TEXT,
    severity              INTEGER,
    similarity            FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.source,
        d.pathology_fr,
        d.text,
        d.description_narrative,
        d.red_flags,
        d.severity,
        (1 - (d.embedding <=> query_embedding))::FLOAT AS similarity
    FROM pathology_documents d
    WHERE d.embedding IS NOT NULL
      AND (1 - (d.embedding <=> query_embedding)) >= min_similarity
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ==========================================================================
-- FONCTION : search_similar_patients — Pool 2
-- Filtre démographique : âge ± age_range et/ou sexe
-- ==========================================================================
CREATE OR REPLACE FUNCTION search_similar_patients(
    query_embedding vector(768),
    match_count     INTEGER DEFAULT 5,
    min_similarity  FLOAT DEFAULT 0.20,
    p_age           INTEGER DEFAULT NULL,
    p_sex           CHAR(1) DEFAULT NULL,
    age_range       INTEGER DEFAULT 15
)
RETURNS TABLE (
    id                     TEXT,
    source                 TEXT,
    pathology_fr           TEXT,
    age                    INTEGER,
    sex                    CHAR(1),
    text                   TEXT,
    differential_diagnosis TEXT,
    similarity             FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.source,
        d.pathology_fr,
        d.age,
        d.sex,
        d.text,
        d.differential_diagnosis,
        (1 - (d.embedding <=> query_embedding))::FLOAT AS similarity
    FROM patient_descriptions d
    WHERE d.embedding IS NOT NULL
      AND (1 - (d.embedding <=> query_embedding)) >= min_similarity
      AND (p_age IS NULL OR d.age BETWEEN p_age - age_range AND p_age + age_range)
      AND (p_sex IS NULL OR d.sex = p_sex)
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ==========================================================================
-- FONCTION : search_clinical_cases — Pool 3
-- Cas cliniques réels (mtsamples)
-- ==========================================================================
CREATE OR REPLACE FUNCTION search_clinical_cases(
    query_embedding vector(768),
    match_count     INTEGER DEFAULT 3,
    min_similarity  FLOAT DEFAULT 0.25
)
RETURNS TABLE (
    id                TEXT,
    source            TEXT,
    medical_specialty TEXT,
    chief_complaint   TEXT,
    assessment        TEXT,
    text              TEXT,
    similarity        FLOAT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.id,
        d.source,
        d.medical_specialty,
        d.chief_complaint,
        d.assessment,
        d.text,
        (1 - (d.embedding <=> query_embedding))::FLOAT AS similarity
    FROM clinical_cases d
    WHERE d.embedding IS NOT NULL
      AND (1 - (d.embedding <=> query_embedding)) >= min_similarity
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ==========================================================================
-- TABLE : users — profils utilisateurs
-- ==========================================================================
CREATE TABLE IF NOT EXISTS users (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    email      TEXT UNIQUE NOT NULL,
    password   TEXT NOT NULL,
    age        INTEGER,
    sex        CHAR(1),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================================================
-- TABLE : sessions — tokens de connexion
-- ==========================================================================
CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================================================
-- TABLE : conversations — une conversation par utilisateur
-- ==========================================================================
CREATE TABLE IF NOT EXISTS conversations (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================================================
-- TABLE : conversation_messages — historique des messages
-- ==========================================================================
CREATE TABLE IF NOT EXISTS conversation_messages (
    id              BIGSERIAL PRIMARY KEY,
    conversation_id TEXT NOT NULL REFERENCES conversations(id),
    role            TEXT NOT NULL,   -- 'user' ou 'assistant'
    content         TEXT NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

DO $$
BEGIN
    RAISE NOTICE '=== PostgreSQL MedRAG v2 initialise ===';
    RAISE NOTICE 'Tables : pathology_documents, patient_descriptions, clinical_cases, query_logs';
    RAISE NOTICE 'Tables : users, sessions, conversations, conversation_messages';
    RAISE NOTICE 'Fonctions : search_pathologies, search_similar_patients, search_clinical_cases';
END $$;
