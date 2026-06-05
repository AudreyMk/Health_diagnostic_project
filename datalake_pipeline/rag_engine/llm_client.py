"""
Agent conversationnel MedRAG — triage structuré + fiche pré-consultation.
"""
import json
import re
from datetime import datetime, timezone

import anthropic

from .config import (
    ANTHROPIC_API_KEY, CLAUDE_MODEL,
    TOP_K_PATHOLOGIES, TOP_K_PATIENTS, TOP_K_CLINICAL,
    MIN_SIMILARITY, AGE_RANGE,
)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

SYSTEM_PROMPT = """Tu es MedRAG, assistant de pré-triage médical français pour tous les patients.

━━ PROCESSUS ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ÉTAPE 1 — RECUEIL (max 3 questions, une par tour)
Collecte : symptôme principal + localisation corporelle, durée, intensité (/10), fièvre (température ?), signes associés.
Si le premier message décrit une urgence évidente → passe directement à l'étape 3.

ÉTAPE 2 — ANALYSE
Dès que tu as assez d'informations → appelle l'outil `chercher_informations_medicales`.

ÉTAPE 3 — RÉPONSE FINALE (structure obligatoire)

---
**Synthèse**
[1-2 phrases sur ce que tu as compris des symptômes]

**Pathologies possibles** *(base médicale MedRAG)*
- **[Nom exact]** — [explication accessible en 1 ligne]
- **[Nom exact]** — [explication accessible en 1 ligne]

**⚠️ Signes d'alarme** *(si détectés)*
[Liste les signes justifiant une orientation urgente]

**Orientation recommandée**
[emoji + niveau] — [justification en 1 phrase]

**Structures de santé dans votre secteur**
[Utilise EXACTEMENT les établissements fournis par l'outil RAG, avec leur nom et numéro de téléphone réels]
[Si aucun établissement fourni → "Activez la localisation pour voir les établissements proches"]
---

Termine TOUJOURS une réponse de triage final avec ce bloc (ne l'affiche pas, il est traité automatiquement) :
<TRIAGE>{"orientation":"domicile|pharmacien|medecin|urgent|samu","color":"green|yellow|orange|red","hypotheses":[{"label":"Nom pathologie","conf":0.80}],"summary":"Résumé symptômes en 1 phrase"}</TRIAGE>

━━ RÈGLES ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Langue : français, chaleureux et professionnel
- Maximum 3 questions avant le triage
- URGENCE (douleur thoracique, AVC, difficulté respiratoire, etc.) → orienter SAMU 15 immédiatement
- Toujours citer les pathologies par leur NOM MÉDICAL avec explication simple
- Citer les vrais établissements FINESS fournis par l'outil (nom + téléphone)
- Terminer en rappelant que MedRAG est un outil d'orientation, non un médecin
- Ne jamais inventer des noms d'établissements"""

# ── Prompt pour la fiche pré-consultation (second appel léger) ────────────────

REPORT_PROMPT = """Tu es MedRAG. Analyse la conversation ci-dessous et extrais les informations structurées.

Réponds UNIQUEMENT avec un bloc JSON valide entre les balises <REPORT> et </REPORT>.
Ne génère rien d'autre. Pas de texte avant ni après.

Structure JSON exacte à respecter :
{
  "main_symptom":  "symptôme principal en 1 phrase courte",
  "duration":      "durée exprimée simplement (ex: 3 jours, depuis ce matin) ou null",
  "intensity":     "chiffre entier /10 si mentionné ou null",
  "associated":    ["symptôme associé 1", "symptôme associé 2"],
  "context":       "antécédents, traitements, allergies mentionnés par le patient. Chaîne vide si rien.",
  "warning_signs": ["signe d'alarme 1", "signe d'alarme 2"],
  "questions":     ["Question utile pour le médecin 1", "Question 2", "Question 3"]
}

Règles strictes :
- main_symptom : 1 phrase, neutre, sans diagnostic
- duration : ce que le patient a dit exactement, pas d'interprétation
- intensity : entier entre 1 et 10, null si jamais mentionné
- associated : liste vide [] si aucun
- context : uniquement ce que le patient a mentionné spontanément (pas d'invention)
- warning_signs : liste vide [] si aucun signe d'alarme détecté
- questions : exactement 2 à 3 questions ouvertes, pertinentes selon les hypothèses de la conversation
- Ne jamais affirmer un diagnostic
- Ne jamais recommander un traitement
- Ne jamais minimiser un symptôme

CONVERSATION :
"""

TOOLS = [{
    "name": "chercher_informations_medicales",
    "description": (
        "Consulte la base médicale MedRAG (pathologies ICD-11/DDXPlus, cas patients, "
        "cas cliniques réels, établissements FINESS du département) pour analyser les "
        "symptômes et trouver les structures de santé proches. Appelle cet outil dès "
        "que tu as les informations essentielles sur les symptômes."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "symptomes": {
                "type": "string",
                "description": "Résumé complet : symptôme principal, localisation, durée, intensité /10, fièvre, signes associés.",
            }
        },
        "required": ["symptomes"],
    },
}]


def _parse_triage(text: str) -> tuple[str, dict | None]:
    """Extrait le bloc <TRIAGE>...</TRIAGE> et retourne (texte_propre, dict|None)."""
    match = re.search(r"<TRIAGE>(.*?)</TRIAGE>", text, re.DOTALL)
    if not match:
        return text, None
    try:
        triage = json.loads(match.group(1).strip())
        clean  = (text[: match.start()] + text[match.end() :]).strip()
        return clean, triage
    except json.JSONDecodeError:
        return text, None


def _generate_report(conversation: list[dict]) -> dict | None:
    """
    Second appel Claude léger : extrait la fiche pré-consultation structurée.
    Pas de tools, pas de RAG — juste l'analyse de la conversation.
    Retourne un dict ou None si échec (la fiche est optionnelle, jamais bloquante).
    """
    # Reconstitue la conversation en texte lisible (ignore les tool_result)
    lines = []
    for msg in conversation:
        role = "Patient" if msg["role"] == "user" else "MedRAG"
        content = msg.get("content", "")
        # Ignore les blocs tool_result (listes de dicts)
        if isinstance(content, str):
            lines.append(f"{role}: {content}")

    conv_text = "\n".join(lines)

    try:
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,   # fiche courte
            system="Tu es un assistant médical qui extrait des données structurées.",
            messages=[{"role": "user", "content": REPORT_PROMPT + conv_text}],
        )
        raw   = resp.content[0].text
        match = re.search(r"<REPORT>(.*?)</REPORT>", raw, re.DOTALL)
        if not match:
            return None
        report = json.loads(match.group(1).strip())
        # Ajoute la date de génération (UTC ISO)
        report["generated_at"] = datetime.now(timezone.utc).isoformat()
        return report
    except Exception:
        return None   # jamais bloquant


def _execute_search(symptomes: str, embed_fn, pg, mongo, age, sex, dept) -> str:
    """Exécute les 3 pools PostgreSQL + FINESS MongoDB."""
    embedding   = embed_fn("query: " + symptomes)
    pathologies = pg.search_pathologies(embedding, TOP_K_PATHOLOGIES, MIN_SIMILARITY)
    patients    = pg.search_similar_patients(embedding, TOP_K_PATIENTS, 0.20, age, sex, AGE_RANGE)
    clinical    = pg.search_clinical_cases(embedding, TOP_K_CLINICAL, MIN_SIMILARITY)

    parts = []

    if pathologies:
        parts.append("=== BASE MEDICALE — Pathologies correspondantes ===")
        for p in pathologies:
            line = f"- {p['pathology_fr']} (correspondance {p['similarity']:.0%})"
            if p.get("red_flags"):
                line += f"  [SIGNES ALARME: {p['red_flags']}]"
            parts.append(line)

    if patients:
        parts.append("=== Cas patients similaires ===")
        for p in patients:
            sexe = "H" if p.get("sex") == "M" else "F"
            parts.append(f"- {p['pathology_fr']} | {p.get('age','?')} ans, {sexe}")

    if clinical:
        parts.append("=== Cas cliniques réels (MTSamples) ===")
        for c in clinical:
            parts.append(f"- {c.get('medical_specialty','—')}: {c.get('assessment','—')}")

    if dept and mongo:
        centers = mongo.search_by_dept(dept, limit=5)
        if centers:
            parts.append(f"\n=== ÉTABLISSEMENTS DE SANTÉ — Département {dept} ===")
            for c in centers:
                parts.append(
                    f"- {c['name']} | {c.get('category_label','')} | "
                    f"{c.get('address','')} | Tél: {c.get('phone','N/A')}"
                )
        else:
            parts.append(f"\n=== Aucun établissement FINESS pour le département {dept} ===")
    elif not dept:
        parts.append("\n=== Localisation non renseignée — établissements indisponibles ===")

    return "\n".join(parts) if parts else "Aucun résultat dans la base médicale."


def _build_patient_context(profile: dict | None, age, sex, dept) -> str:
    """
    Construit le bloc contexte patient injecté dans le system prompt.
    Inputs sanitisés : longueur max par champ pour prévenir le prompt injection.
    Retourne une chaîne vide si aucune donnée disponible.
    """
    lines = []
    if age:  lines.append(f"- Âge : {age} ans")
    if sex:  lines.append(f"- Sexe : {'Homme' if sex == 'M' else 'Femme'}")
    if dept: lines.append(f"- Département : {dept}")

    if profile:
        ants = profile.get("antecedents") or []
        if ants:
            safe = [str(a)[:100] for a in ants[:10]]
            lines.append(f"- Antécédents : {', '.join(safe)}")

        txs = profile.get("treatments") or []
        if txs:
            labels = [f"{str(t.get('name',''))[:80]} ({t.get('type','')})" for t in txs[:10]]
            lines.append(f"- Traitements en cours : {', '.join(labels)}")

        allgs = profile.get("allergies") or []
        if allgs:
            safe_a = [str(a)[:80] for a in allgs[:10]]
            lines.append(f"- Allergies connues : {', '.join(safe_a)}")

        ls = profile.get("lifestyle") or {}
        if ls.get("smoking")  and ls["smoking"]  != "unknown":
            lines.append(f"- Tabac : {ls['smoking']}")
        if ls.get("activity") and ls["activity"] != "unknown":
            lines.append(f"- Activité physique : {ls['activity']}")

    if not lines:
        return ""

    return (
        "<patient_profile>\n"
        + "\n".join(lines)
        + "\nNote : ces informations sont déclaratives — vérifiez leur pertinence avec le patient.\n"
        + "</patient_profile>"
    )


def chat(messages: list[dict], embed_fn, pg, mongo=None,
         age=None, sex=None, dept=None, profile=None) -> dict:
    """
    Boucle agentique MedRAG.
    Retourne {"text": str, "triage": dict|None, "report": dict|None}.
    profile : dict du profil médical patient_profiles (None si pas de profil).
    """
    system = SYSTEM_PROMPT
    ctx = _build_patient_context(profile, age, sex, dept)
    if ctx:
        system += f"\n\n{ctx}"

    working = list(messages)

    while True:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1600,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=TOOLS,
            messages=working,
        )

        if response.stop_reason == "tool_use":
            tool   = next(b for b in response.content if b.type == "tool_use")
            result = _execute_search(
                tool.input.get("symptomes", ""), embed_fn, pg, mongo, age, sex, dept
            )
            working.append({"role": "assistant", "content": response.content})
            working.append({
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": tool.id, "content": result}],
            })
        else:
            raw_text   = next(b.text for b in response.content if hasattr(b, "text"))
            clean_text, triage = _parse_triage(raw_text)

            # Génère la fiche uniquement quand le triage est disponible
            report = _generate_report(working) if triage is not None else None

            return {"text": clean_text, "triage": triage, "report": report}
