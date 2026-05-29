"""
Configuration globale des tests.

Stratégie :
- sentence_transformers et torch sont mockés au niveau de sys.modules
  pour éviter de télécharger le modèle 600 Mo en CI.
- Les connexions DB (psycopg2, pymongo) sont mockées dans chaque test.
- L'API FastAPI est testée avec TestClient en patchant ses dépendances.
"""
import sys
from unittest.mock import MagicMock

import pytest

# ── Mock des dépendances lourdes AVANT tout import du projet ──────────────────
# sentence_transformers (600 Mo) et torch ne sont pas installés en CI dev.
_HEAVY = ["sentence_transformers", "torch", "tqdm"]
for _mod in _HEAVY:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Après le mock sys.modules, on peut importer librement le code projet


@pytest.fixture
def sample_embedding() -> list[float]:
    """Embedding factice de dimension 768 (multilingual-e5-base)."""
    return [0.01] * 768


@pytest.fixture
def sample_pathology_doc() -> dict:
    return {
        "id": "patho_abc123",
        "source": "ddxplus",
        "pathology": "Pneumonie",
        "text": (
            "Pathologie : Pneumonie (Pneumonia). Code CIM-10 : J18. "
            "Sévérité : grave. Symptômes : toux ; fièvre ; douleur thoracique."
        ),
        "similarity": 0.82,
    }


@pytest.fixture
def sample_patient_doc() -> dict:
    return {
        "id": "patient_def456",
        "source": "ddxplus",
        "pathology": "Pneumonie",
        "text": "Patient homme de 45 ans. Symptômes : toux ; fièvre ; douleur thoracique.",
        "similarity": 0.75,
    }


@pytest.fixture
def sample_health_center() -> dict:
    return {
        "id": "finess_123456789",
        "finess_id": "123456789",
        "name": "CHU de Paris",
        "category": "Centre Hospitalier Universitaire (C.H.U.)",
        "category_code": "355",
        "address": "1 Rue de la Paix, 75001 Paris",
        "city": "Paris",
        "department": "Paris",
        "phone": "01 40 00 00 00",
        "location": {"type": "Point", "coordinates": [2.3310, 48.8736]},
    }


@pytest.fixture
def mock_engine_result(sample_pathology_doc, sample_patient_doc, sample_health_center):
    """Résultat complet simulé du MedRAGEngine."""
    return {
        "query": "fièvre toux douleur thoracique",
        "patient_info": {"age": 45, "sex": "M"},
        "pathologies_retrieved": [sample_pathology_doc],
        "similar_patients": [sample_patient_doc],
        "nearby_centers": [sample_health_center],
        "llm_response": "## Analyse\nFièvre + toux → suspicion pneumonie.",
        "llm_usage": {"input_tokens": 500, "output_tokens": 200, "cache_read_tokens": 0, "cache_write_tokens": 0},
        "performance": {
            "embed_seconds": 0.05,
            "pg_seconds": 0.1,
            "mongo_seconds": 0.05,
            "llm_seconds": 1.2,
            "total_seconds": 1.4,
        },
        "retrieval_stats": {
            "pathologies_found": 1,
            "patients_found": 1,
            "centers_found": 1,
            "top_similarity": 0.82,
        },
    }
