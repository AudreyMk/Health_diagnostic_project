"""
Agent conversationnel MedRAG — triage structuré + fiche pré-consultation.

Les prompts ne sont PAS écrits ici : ils vivent dans le dossier prompts/
(versionnés, sourcés, traçables — voir prompts/README.md) et sont chargés
au démarrage via prompt_loader.py.
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
from .prompt_loader import load_system_prompt, load_report_prompt

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Chargés une seule fois au démarrage : le texte reste stable pendant toute
# la vie du process → le prompt caching Anthropic fonctionne normalement.
SYSTEM_PROMPT = load_system_prompt()
REPORT_PROMPT = load_report_prompt() + "\n\nCONVERSATION :\n"

# Garde-fou de la boucle agentique : nombre max d'allers-retours outil.
MAX_ITERATIONS = 4

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


def _generate_report(conversation: list[dict], profile: dict | None = None,
                     age=None, sex=None) -> dict | None:
    """
    Second appel Claude léger : extrait la fiche pré-consultation structurée.
    Pas de tools, pas de RAG — analyse de la conversation + profil patient.
    Le profil est injecté pour que la fiche destinée au médecin contienne
    les antécédents/traitements/allergies même si le patient ne les a pas
    répétés dans la conversation.
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

    # Bloc profil patient (base de données) — à intégrer dans le champ "context"
    profile_lines = []
    if age:
        profile_lines.append(f"- Âge : {age} ans")
    if sex:
        profile_lines.append(f"- Sexe : {'Homme' if sex == 'M' else 'Femme'}")
    if profile:
        ants = profile.get("antecedents") or []
        if ants:
            profile_lines.append(f"- Antécédents : {', '.join(str(a)[:80] for a in ants[:5])}")
        txs = profile.get("treatments") or []
        if txs:
            profile_lines.append(f"- Traitements : {', '.join(str(t.get('name',''))[:60] for t in txs[:5])}")
        allgs = profile.get("allergies") or []
        if allgs:
            profile_lines.append(f"- Allergies : {', '.join(str(a)[:60] for a in allgs[:5])}")

    profile_text = ""
    if profile_lines:
        profile_text = "PROFIL PATIENT (base de données) :\n" + "\n".join(profile_lines) + "\n\n"

    try:
        resp = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,   # fiche courte
            system="Tu es un assistant médical qui extrait des données structurées.",
            messages=[{"role": "user", "content": REPORT_PROMPT + profile_text + conv_text}],
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


def _execute_search(symptomes: str, embed_fn, pg, mongo, age, sex, dept,
                    lat=None, lon=None) -> str:
    """Exécute les 3 pools PostgreSQL + FINESS MongoDB.

    Recherche d'établissements :
    - si lat/lon connus  → search_nearby (rayon 50 km) + fallback search_by_dept si vide
    - sinon              → search_by_dept (centroïde département)
    """
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

    if mongo:
        centers = []
        source  = None

        # Priorité 1 : recherche géolocalisée si on connaît la position du patient
        if lat is not None and lon is not None:
            centers = mongo.search_nearby(
                longitude=lon, latitude=lat,
                max_distance=50_000,   # 50 km
                limit=5,
            )
            if centers:
                source = f"à proximité (rayon 50 km autour de votre position)"

        # Fallback : recherche par département
        if not centers and dept:
            centers = mongo.search_by_dept(dept, limit=5)
            if centers:
                source = f"département {dept}"

        if centers:
            parts.append(f"\n=== ÉTABLISSEMENTS DE SANTÉ — {source} ===")
            for c in centers:
                parts.append(
                    f"- {c['name']} | {c.get('category_label','')} | "
                    f"{c.get('address','')} | Tél: {c.get('phone','N/A')}"
                )
        elif dept:
            parts.append(f"\n=== Aucun établissement FINESS pour le département {dept} ===")
        else:
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
         age=None, sex=None, dept=None, profile=None,
         lat=None, lon=None, prev_triage=None) -> dict:
    """
    Boucle agentique MedRAG.
    Retourne {"text": str, "triage": dict|None, "report": dict|None}.
    profile     : dict du profil médical patient_profiles (None si pas de profil).
    lat, lon    : coordonnées WGS84 du patient (optionnelles) — si fournies, la
                  recherche d'établissements est géolocalisée ($near).
    prev_triage : triage déjà émis dans cette conversation (None si premier tour).
                  Si présent → mode follow-up : règle du cliquet rappelée à l'agent
                  (l'application en code est faite dans api.py).
    """
    system = SYSTEM_PROMPT
    ctx = _build_patient_context(profile, age, sex, dept)
    if ctx:
        system += f"\n\n{ctx}"

    # Mode follow-up : une orientation existe déjà → rappel explicite du cliquet
    if prev_triage and prev_triage.get("orientation"):
        system += (
            "\n\n<triage_precedent>\n"
            f"Une orientation a DÉJÀ été émise dans cette conversation : "
            f"{prev_triage['orientation']}.\n"
            "Tu es en mode SUIVI (voir référence 4) : ne propose JAMAIS une "
            "orientation moins urgente. Réémets un <TRIAGE> uniquement si un "
            "élément clinique nouveau justifie une orientation PLUS urgente.\n"
            "</triage_precedent>"
        )

    working = list(messages)

    # Boucle bornée : évite une boucle infinie si le LLM enchaîne les appels outil
    for _ in range(MAX_ITERATIONS):
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2200,   # marge pour réponse complète + bloc <TRIAGE> non tronqué
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=TOOLS,
            messages=working,
        )

        if response.stop_reason == "tool_use":
            tool   = next(b for b in response.content if b.type == "tool_use")
            result = _execute_search(
                tool.input.get("symptomes", ""), embed_fn, pg, mongo, age, sex, dept,
                lat=lat, lon=lon,
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
            # (le profil patient est injecté pour une fiche complète côté médecin)
            report = (
                _generate_report(working, profile=profile, age=age, sex=sex)
                if triage is not None else None
            )

            return {"text": clean_text, "triage": triage, "report": report}

    # Limite d'itérations atteinte : réponse de repli sûre, jamais de crash
    return {
        "text": (
            "Je n'ai pas pu finaliser l'analyse de votre situation. "
            "Par prudence, je vous recommande de contacter un professionnel de santé. "
            "En cas d'urgence, appelez le 15 (SAMU)."
        ),
        "triage": None,
        "report": None,
    }
