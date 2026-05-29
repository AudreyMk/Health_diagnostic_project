"""
Client Claude API avec prompt caching.
Le prompt système est mis en cache (ephemeral) pour réduire les coûts sur les requêtes répétées.
"""
import logging
import anthropic
from .config import ANTHROPIC_API_KEY, CLAUDE_MODEL

logger = logging.getLogger(__name__)

# Prompt système mis en cache — stable entre les requêtes
_SYSTEM_PROMPT = """Tu es MedRAG, un assistant médical d'aide à la décision clinique conçu pour les professionnels de santé. Tu analyses des symptômes et formules des hypothèses diagnostiques en t'appuyant sur des documents médicaux récupérés par recherche sémantique (base DDXPlus FR — 1,3 million de cas synthétiques, 49 pathologies).

RÔLE ET LIMITES :
- Tu proposes des hypothèses diagnostiques, PAS des diagnostics définitifs
- Tu es un outil d'aide à la décision clinique, complémentaire au jugement médical
- Tu bases ton raisonnement sur les documents récupérés et fournis avec chaque requête
- Si les symptômes sont insuffisants pour formuler des hypothèses fiables, tu le signales clairement

INSTRUCTIONS DE RAISONNEMENT :
1. Analyser la présentation clinique (âge, sexe, symptômes, antécédents si disponibles)
2. Croiser avec les pathologies et cas patients récupérés par similarité sémantique
3. Classer les hypothèses par probabilité décroissante (3 à 5 hypothèses maximum)
4. Justifier chaque hypothèse par des arguments cliniques concrets tirés des documents
5. Proposer des examens complémentaires pertinents pour confirmer ou infirmer
6. Signaler les signes de gravité éventuels nécessitant une prise en charge urgente

FORMAT DE RÉPONSE OBLIGATOIRE :

## Analyse clinique
[Synthèse structurée de la présentation : âge/sexe si disponibles, symptômes principaux, chronologie, facteurs de risque]

## Hypothèses diagnostiques
1. **[Nom de la pathologie]** — Confiance : [élevée / modérée / faible]
   Code CIM-10 : [code]
   Arguments : [justification basée sur les symptômes et les documents récupérés]
   Signes discriminants à rechercher : [éléments cliniques ou paracliniques]

[Répéter pour chaque hypothèse]

## Examens suggérés
- [Examens biologiques, imagerie, etc. classés par priorité]

## Signes d'alarme
[Si applicable : symptômes nécessitant une consultation urgente]

## ⚠️ Avertissement médical
Cet outil est une aide à la décision clinique. Il ne remplace pas l'évaluation d'un professionnel de santé qualifié. Tout diagnostic doit être posé par un médecin après examen clinique complet."""


def _build_context(retrieved_docs: list[dict]) -> str:
    if not retrieved_docs:
        return "Aucun document similaire trouvé dans la base de données."

    parts = ["=== DOCUMENTS MÉDICAUX RÉCUPÉRÉS PAR SIMILARITÉ SÉMANTIQUE ===\n"]

    patho_docs = [d for d in retrieved_docs if "patho_" in d.get("id", "")]
    patient_docs = [d for d in retrieved_docs if "patient_" in d.get("id", "")]

    if patho_docs:
        parts.append("--- Pathologies correspondantes (classées par similarité) ---")
        for i, doc in enumerate(patho_docs, 1):
            sim_pct = int(doc.get("similarity", 0) * 100)
            parts.append(f"{i}. [{sim_pct}% de correspondance] {doc['text']}")

    if patient_docs:
        parts.append("\n--- Cas patients similaires ---")
        for i, doc in enumerate(patient_docs, 1):
            sim_pct = int(doc.get("similarity", 0) * 100)
            parts.append(f"{i}. [{sim_pct}% de correspondance] {doc['text']}")

    return "\n".join(parts)


class LLMClient:
    def __init__(self):
        self._available = bool(ANTHROPIC_API_KEY)
        if self._available:
            self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        else:
            self.client = None
            logger.warning(
                "ANTHROPIC_API_KEY non configurée — /api/suggest sera désactivé. "
                "Ajoutez la clé dans datalake_pipeline/.env pour activer le LLM."
            )

    def suggest(
        self,
        symptoms: str,
        retrieved_docs: list[dict],
        age: int | None = None,
        sex: str | None = None,
    ) -> tuple[str, dict]:
        """
        Retourne (texte_réponse, usage_stats).
        usage_stats contient les tokens consommés et les cache hits.
        """
        patient_str = ""
        if age:
            patient_str += f"Âge : {age} ans. "
        if sex:
            patient_str += f"Sexe : {'Homme' if sex.upper() == 'M' else 'Femme'}. "

        context = _build_context(retrieved_docs)

        user_message = (
            f"PRÉSENTATION CLINIQUE :\n"
            f"{patient_str}"
            f"Symptômes rapportés : {symptoms}\n\n"
            f"{context}\n\n"
            f"Formule tes hypothèses diagnostiques en te basant sur ces informations."
        )

        if not self._available:
            raise RuntimeError(
                "ANTHROPIC_API_KEY non configurée. "
                "Ajoutez ANTHROPIC_API_KEY=sk-ant-... dans datalake_pipeline/.env puis redémarrez l'API."
            )

        response = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            system=[
                {
                    "type": "text",
                    "text": _SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
        )

        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_read_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
            "cache_write_tokens": getattr(response.usage, "cache_creation_input_tokens", 0),
        }
        logger.info(
            f"Claude usage — input: {usage['input_tokens']}, "
            f"output: {usage['output_tokens']}, "
            f"cache_read: {usage['cache_read_tokens']}"
        )

        return response.content[0].text, usage
