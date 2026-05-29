"""
Tests unitaires — PGRetriever & MongoRetriever
Les connexions aux bases de données sont intégralement mockées.
"""
from unittest.mock import MagicMock, patch, call
import pytest


# ── PGRetriever ───────────────────────────────────────────────────────────────

class TestPGRetriever:
    @pytest.fixture(autouse=True)
    def mock_pool(self, monkeypatch):
        """Mock du pool de connexions PostgreSQL."""
        self.mock_conn = MagicMock()
        self.mock_cursor = MagicMock()
        self.mock_cursor.__enter__ = MagicMock(return_value=self.mock_cursor)
        self.mock_cursor.__exit__ = MagicMock(return_value=False)
        self.mock_conn.cursor.return_value = self.mock_cursor

        pool = MagicMock()
        pool.getconn.return_value = self.mock_conn
        pool.putconn = MagicMock()

        with patch("rag_engine.retriever.psycopg2.pool.ThreadedConnectionPool", return_value=pool):
            from rag_engine.retriever import PGRetriever
            self.retriever = PGRetriever()
            self.pool = pool

    def test_search_calls_stored_function(self, sample_embedding):
        """search() doit appeler search_similar_documents avec les bons paramètres."""
        self.mock_cursor.fetchall.return_value = []

        self.retriever.search(sample_embedding, top_k=5, min_similarity=0.3)

        self.mock_cursor.execute.assert_called_once()
        sql = self.mock_cursor.execute.call_args[0][0]
        assert "search_similar_documents" in sql

    def test_search_returns_list_of_dicts(self, sample_embedding, sample_pathology_doc):
        """search() doit retourner une liste de dicts."""
        self.mock_cursor.fetchall.return_value = [sample_pathology_doc]

        # RealDictCursor retourne des objets dict-like
        with patch("rag_engine.retriever.psycopg2.extras.RealDictCursor"):
            result = self.retriever.search(sample_embedding)

        assert isinstance(result, list)

    def test_search_releases_connection(self, sample_embedding):
        """La connexion doit être remise dans le pool après search()."""
        self.mock_cursor.fetchall.return_value = []

        self.retriever.search(sample_embedding)

        self.pool.putconn.assert_called_once_with(self.mock_conn)

    def test_search_releases_connection_on_error(self, sample_embedding):
        """La connexion doit être remise même en cas d'erreur."""
        self.mock_cursor.execute.side_effect = Exception("DB error")

        with pytest.raises(Exception):
            self.retriever.search(sample_embedding)

        self.pool.putconn.assert_called_once_with(self.mock_conn)

    def test_get_stats_returns_dict(self):
        """get_stats() doit retourner un dictionnaire avec les compteurs."""
        self.mock_cursor.fetchone.return_value = (49, 43981, 49, 43981)

        with patch("rag_engine.retriever.psycopg2.extras.RealDictCursor"):
            stats = self.retriever.get_stats()

        assert "pathologies" in stats
        assert "patients" in stats


# ── MongoRetriever ────────────────────────────────────────────────────────────

class TestMongoRetriever:
    @pytest.fixture(autouse=True)
    def mock_mongo(self):
        """Mock du client MongoDB."""
        self.mock_collection = MagicMock()
        self.mock_db = MagicMock()
        self.mock_db.__getitem__ = MagicMock(return_value=self.mock_collection)
        self.mock_client = MagicMock()
        self.mock_client.__getitem__ = MagicMock(return_value=self.mock_db)

        with patch("rag_engine.retriever.MongoClient", return_value=self.mock_client):
            from rag_engine.retriever import MongoRetriever
            self.retriever = MongoRetriever()

    def _mock_cursor(self, docs: list) -> MagicMock:
        """Crée un curseur MongoDB factice chaînable (find().limit())."""
        cursor = MagicMock()
        cursor.limit.return_value = iter(docs)
        return cursor

    def test_search_nearby_uses_near_query(self, sample_health_center):
        """search_nearby() doit utiliser l'opérateur $near de MongoDB."""
        doc = dict(sample_health_center)
        doc["_id"] = "abc"
        self.mock_collection.find.return_value = self._mock_cursor([doc])

        self.retriever.search_nearby(
            longitude=2.3522, latitude=48.8566,
            max_distance=10000, limit=5,
        )

        call_args = self.mock_collection.find.call_args[0][0]
        assert "$near" in call_args.get("location", {})

    def test_search_nearby_removes_id_field(self, sample_health_center):
        """Les documents retournés ne doivent pas contenir _id."""
        doc = dict(sample_health_center)
        doc["_id"] = "mongo_internal_id"
        self.mock_collection.find.return_value = self._mock_cursor([doc])

        results = self.retriever.search_nearby(2.3522, 48.8566)

        assert all("_id" not in r for r in results)

    def test_search_nearby_filters_by_category(self):
        """Le filtre category_codes doit être inclus dans la requête MongoDB."""
        self.mock_collection.find.return_value = self._mock_cursor([])

        self.retriever.search_nearby(
            longitude=2.35, latitude=48.85,
            category_codes=["355", "146"],
        )

        call_args = self.mock_collection.find.call_args[0][0]
        assert "category_code" in call_args
        assert call_args["category_code"]["$in"] == ["355", "146"]

    def test_get_stats_returns_count(self):
        """get_stats() doit retourner le nombre de documents."""
        self.mock_collection.count_documents.return_value = 52154

        stats = self.retriever.get_stats()

        assert stats["health_centers"] == 52154
