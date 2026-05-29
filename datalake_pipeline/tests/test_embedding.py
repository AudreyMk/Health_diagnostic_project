"""
Tests unitaires — EmbeddingManager
sentence_transformers est mocké dans conftest.py.
"""
from unittest.mock import MagicMock, patch
import numpy as np


def test_encode_query_returns_list():
    """encode_query doit retourner une liste de floats."""
    with patch("rag_engine.embedding_manager.SentenceTransformer") as mock_st:
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1] * 768)
        mock_st.return_value = mock_model

        from rag_engine.embedding_manager import EmbeddingManager
        em = EmbeddingManager()
        result = em.encode_query("fièvre et toux")

    assert isinstance(result, list)
    assert len(result) == 768
    assert all(isinstance(v, float) for v in result)


def test_encode_query_applies_prefix():
    """Le préfixe 'query: ' doit être ajouté au texte avant encodage."""
    with patch("rag_engine.embedding_manager.SentenceTransformer") as mock_st:
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.0] * 768)
        mock_st.return_value = mock_model

        from rag_engine.embedding_manager import EmbeddingManager
        em = EmbeddingManager()
        em.encode_query("douleur abdominale")

        call_args = mock_model.encode.call_args
        assert call_args[0][0].startswith("query: ")
        assert "douleur abdominale" in call_args[0][0]


def test_encode_batch_applies_prefix():
    """encode_batch doit préfixer chaque texte avec 'passage: ' par défaut."""
    with patch("rag_engine.embedding_manager.SentenceTransformer") as mock_st:
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1] * 768, [0.2] * 768])
        mock_st.return_value = mock_model

        from rag_engine.embedding_manager import EmbeddingManager
        em = EmbeddingManager()
        texts = ["symptôme A", "symptôme B"]
        result = em.encode_batch(texts)

    assert len(result) == 2
    assert all(len(emb) == 768 for emb in result)

    call_args = mock_model.encode.call_args[0][0]
    assert all(t.startswith("passage: ") for t in call_args)
