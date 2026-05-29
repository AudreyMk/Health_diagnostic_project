"""
Gestionnaire d'embeddings — chargement unique du modèle sentence-transformers.
Utilise le même modèle que load_to_databases.py (multilingual-e5-base, 768 dims).
"""
import logging
from sentence_transformers import SentenceTransformer
from .config import EMBEDDING_MODEL

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """
    Charge le modèle une seule fois et encode les requêtes utilisateur.
    Les modèles e5 nécessitent le préfixe "query: " pour les requêtes
    et "passage: " pour les documents (cohérent avec load_to_databases.py).
    """

    def __init__(self):
        logger.info(f"Chargement du modèle d'embedding : {EMBEDDING_MODEL}")
        self.model = SentenceTransformer(EMBEDDING_MODEL)
        logger.info("Modèle chargé.")

    def encode_query(self, text: str) -> list[float]:
        embedding = self.model.encode(
            f"query: {text}",
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return embedding.tolist()

    def encode_batch(self, texts: list[str], prefix: str = "passage: ") -> list[list[float]]:
        prefixed = [f"{prefix}{t}" for t in texts]
        embeddings = self.model.encode(
            prefixed,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,
        )
        return [e.tolist() for e in embeddings]
