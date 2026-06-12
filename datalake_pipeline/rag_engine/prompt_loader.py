"""
prompts.py — Chargement des prompts depuis le dossier prompts/.

Aucun prompt n'est écrit en dur dans le code : tout le contenu textuel
injecté dans Claude vit dans des fichiers markdown versionnés.
Voir prompts/README.md pour les règles de mise à jour.
"""
import re
from pathlib import Path

# Dossier prompts/ à côté de ce fichier
PROMPTS_DIR = Path(__file__).parent / "prompts"


def _strip_header(text: str) -> str:
    """Retire l'en-tête de versionnage <!-- ... --> du début d'un fichier.
    L'en-tête sert à la traçabilité humaine, pas au LLM (économie de tokens)."""
    return re.sub(r"^\s*<!--.*?-->\s*", "", text, count=1, flags=re.DOTALL)


def load_system_prompt() -> str:
    """Assemble le system prompt : prompt de base + références cliniques.

    Les fichiers references/ sont injectés dans l'ordre de leur numéro
    (01_, 02_, ...). Ajouter une référence = créer un nouveau fichier,
    aucun changement de code nécessaire.
    """
    base = _strip_header(
        (PROMPTS_DIR / "system_prompt.md").read_text(encoding="utf-8")
    )

    references = []
    for ref_file in sorted((PROMPTS_DIR / "references").glob("*.md")):
        references.append(_strip_header(ref_file.read_text(encoding="utf-8")))

    return base + "\n\n" + "\n\n".join(references)


def load_report_prompt() -> str:
    """Charge le prompt d'extraction de la fiche pré-consultation."""
    return _strip_header(
        (PROMPTS_DIR / "report_prompt.md").read_text(encoding="utf-8")
    )
