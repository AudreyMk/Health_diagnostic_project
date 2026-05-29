"""
Tests des endpoints FastAPI — rag_engine/api.py
Les dépendances lourdes (EmbeddingManager, DB, LLM) sont mockées via patch.
"""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_app(mock_engine_result):
    """
    Crée un TestClient avec toutes les dépendances du lifespan mockées.
    Le moteur retourne mock_engine_result sur suggest().
    """
    mock_engine = MagicMock()
    mock_engine.suggest.return_value = mock_engine_result

    mock_pg = MagicMock()
    mock_pg.get_all_pathologies.return_value = [
        {"id": "patho_abc", "pathology_fr": "Pneumonie", "pathology_en": "Pneumonia",
         "icd10": "J18", "severity": 2},
        {"id": "patho_def", "pathology_fr": "Grippe", "pathology_en": "Influenza",
         "icd10": "J11", "severity": 3},
    ]
    mock_pg.get_stats.return_value = {
        "pathologies": 49, "patients": 43981,
        "pathologies_vectorisees": 49, "patients_vectorises": 43981,
    }

    mock_mongo = MagicMock()
    mock_mongo.search_nearby.return_value = [
        {"name": "CHU de Paris", "category_code": "355",
         "location": {"coordinates": [2.33, 48.87]}}
    ]
    mock_mongo.get_stats.return_value = {"health_centers": 52154}

    with (
        patch("rag_engine.api.EmbeddingManager", return_value=MagicMock()),
        patch("rag_engine.api.PGRetriever", return_value=mock_pg),
        patch("rag_engine.api.MongoRetriever", return_value=mock_mongo),
        patch("rag_engine.api.LLMClient", return_value=MagicMock()),
        patch("rag_engine.api.MedRAGEngine", return_value=mock_engine),
    ):
        from rag_engine.api import app
        with TestClient(app) as client:
            # Injecter les mocks dans app.state
            app.state.engine = mock_engine
            app.state.pg = mock_pg
            app.state.mongo = mock_mongo
            yield client, mock_engine, mock_pg, mock_mongo


# ── GET /api/health ───────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self, mock_app):
        client, *_ = mock_app
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_contains_status(self, mock_app):
        client, *_ = mock_app
        data = client.get("/api/health").json()
        assert "status" in data
        assert data["status"] in ("ok", "degraded")

    def test_health_contains_database_info(self, mock_app):
        client, *_ = mock_app
        data = client.get("/api/health").json()
        assert "databases" in data
        assert "postgresql" in data["databases"]
        assert "mongodb" in data["databases"]


# ── GET /api/pathologies ──────────────────────────────────────────────────────

class TestPathologies:
    def test_pathologies_returns_200(self, mock_app):
        client, *_ = mock_app
        resp = client.get("/api/pathologies")
        assert resp.status_code == 200

    def test_pathologies_contains_list(self, mock_app):
        client, *_ = mock_app
        data = client.get("/api/pathologies").json()
        assert "pathologies" in data
        assert isinstance(data["pathologies"], list)

    def test_pathologies_count_matches(self, mock_app):
        client, *_ = mock_app
        data = client.get("/api/pathologies").json()
        assert data["count"] == len(data["pathologies"])


# ── POST /api/suggest ─────────────────────────────────────────────────────────

class TestSuggest:
    VALID_PAYLOAD = {
        "symptoms": "Fièvre à 39°C depuis 3 jours avec toux sèche",
        "age": 45,
        "sex": "M",
    }

    def test_suggest_returns_200(self, mock_app):
        client, *_ = mock_app
        resp = client.post("/api/suggest", json=self.VALID_PAYLOAD)
        assert resp.status_code == 200

    def test_suggest_calls_engine(self, mock_app):
        client, mock_engine, *_ = mock_app
        client.post("/api/suggest", json=self.VALID_PAYLOAD)
        mock_engine.suggest.assert_called_once()

    def test_suggest_passes_symptoms(self, mock_app):
        client, mock_engine, *_ = mock_app
        client.post("/api/suggest", json=self.VALID_PAYLOAD)
        kwargs = mock_engine.suggest.call_args[1]
        assert kwargs["symptoms"] == self.VALID_PAYLOAD["symptoms"]

    def test_suggest_passes_patient_info(self, mock_app):
        client, mock_engine, *_ = mock_app
        client.post("/api/suggest", json=self.VALID_PAYLOAD)
        kwargs = mock_engine.suggest.call_args[1]
        assert kwargs["age"] == 45
        assert kwargs["sex"] == "M"

    def test_suggest_response_structure(self, mock_app, mock_engine_result):
        client, *_ = mock_app
        data = client.post("/api/suggest", json=self.VALID_PAYLOAD).json()
        for key in ("query", "pathologies_retrieved", "llm_response", "performance"):
            assert key in data, f"Clé manquante : {key}"

    def test_suggest_rejects_short_symptoms(self, mock_app):
        client, *_ = mock_app
        resp = client.post("/api/suggest", json={"symptoms": "court"})
        assert resp.status_code == 422

    def test_suggest_rejects_invalid_sex(self, mock_app):
        client, *_ = mock_app
        payload = {**self.VALID_PAYLOAD, "sex": "X"}
        resp = client.post("/api/suggest", json=payload)
        assert resp.status_code == 422

    def test_suggest_with_geolocation(self, mock_app):
        client, mock_engine, *_ = mock_app
        payload = {**self.VALID_PAYLOAD, "latitude": 48.8566, "longitude": 2.3522}
        client.post("/api/suggest", json=payload)
        kwargs = mock_engine.suggest.call_args[1]
        assert kwargs["latitude"] == pytest.approx(48.8566)
        assert kwargs["longitude"] == pytest.approx(2.3522)

    def test_suggest_without_geolocation(self, mock_app):
        client, mock_engine, *_ = mock_app
        client.post("/api/suggest", json=self.VALID_PAYLOAD)
        kwargs = mock_engine.suggest.call_args[1]
        assert kwargs["latitude"] is None
        assert kwargs["longitude"] is None


# ── POST /api/centers ─────────────────────────────────────────────────────────

class TestCenters:
    VALID_PAYLOAD = {"latitude": 48.8566, "longitude": 2.3522}

    def test_centers_returns_200(self, mock_app):
        client, *_ = mock_app
        resp = client.post("/api/centers", json=self.VALID_PAYLOAD)
        assert resp.status_code == 200

    def test_centers_response_contains_list(self, mock_app):
        client, *_ = mock_app
        data = client.post("/api/centers", json=self.VALID_PAYLOAD).json()
        assert "centers" in data
        assert isinstance(data["centers"], list)

    def test_centers_count_matches(self, mock_app):
        client, *_ = mock_app
        data = client.post("/api/centers", json=self.VALID_PAYLOAD).json()
        assert data["count"] == len(data["centers"])

    def test_centers_rejects_invalid_latitude(self, mock_app):
        client, *_ = mock_app
        resp = client.post("/api/centers", json={"latitude": 999, "longitude": 2.35})
        assert resp.status_code == 422


# ── GET / ─────────────────────────────────────────────────────────────────────

def test_root_returns_200(mock_app):
    client, *_ = mock_app
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "name" in data
    assert "docs" in data
