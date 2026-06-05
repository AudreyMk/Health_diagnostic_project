#!/usr/bin/env python3
"""
Phase D — Traitement des cas cliniques mtsamples.

Produit processed/mtsamples_clinical_cases.jsonl :
  ~4 966 cas cliniques anglais (4 999 lignes - 33 sans transcription),
  chacun avec un texte structuré pour l'embedding (multilingual-e5-base).

Extraction par regex des sections ASSESSMENT et HPI depuis la transcription.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import unicodedata
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Patterns de sections cliniques ────────────────────────────────────────────

# Headers qui marquent le début d'une section de diagnostic / évaluation
ASSESSMENT_HEADERS = re.compile(
    r"\b(ASSESSMENT|IMPRESSION|DIAGNOS[IE]S|FINAL DIAGNOSIS|CLINICAL IMPRESSION"
    r"|ASSESSMENT AND PLAN|IMPRESSION/PLAN|ASSESSMENT/PLAN)\s*[:/,]?\s*",
    re.IGNORECASE,
)

# Headers qui marquent le début de l'anamnèse
HPI_HEADERS = re.compile(
    r"\b(HISTORY OF PRESENT ILLNESS|CHIEF COMPLAINT|HPI|SUBJECTIVE"
    r"|REASON FOR VISIT|REASON FOR CONSULTATION|PRESENTING COMPLAINT)\s*[:/,]?\s*",
    re.IGNORECASE,
)

# Header générique pour délimiter la fin d'une section extraite.
# Accepte les deux formats courants dans mtsamples :
#   - Newline suivi d'un header ALL CAPS  (ex: "\nPROCEDURE:")
#   - Virgule inline suivie d'un header   (ex: ",POSTOPERATIVE DIAGNOSES:,")
NEXT_SECTION = re.compile(
    r"(?:(?:\n|\r\n?)\s*|,\s*)"          # séparateur : newline ou virgule
    r"[A-Z][A-Z &/\-]{3,}"               # 1er mot ALL-CAPS (≥ 4 chars)
    r"(?:\s+[A-Z][A-Z &/\-]*)?"          # 2e mot ALL-CAPS optionnel
    r"\s*:\s*,?",                          # deux-points (+ virgule optionnelle)
)

MAX_ASSESSMENT_CHARS = 400  # longueur max pour la section assessment
MAX_HPI_CHARS = 200         # longueur max pour HPI (moins de risque de débordement)
MAX_KEYWORDS = 10           # nombre max de mots-clés conservés

_LEADING_PUNCT = re.compile(r"^[\s,\.;:\-]+")   # ponctuation parasite en début de section


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _extract_section(text: str, header_re: re.Pattern, max_chars: int) -> str:
    """
    Extrait le texte qui suit le premier header correspondant,
    jusqu'au prochain header de section ou max_chars caractères.
    """
    m = header_re.search(text)
    if not m:
        return ""
    start = m.end()
    rest = text[start:]
    # Délimiter par la prochaine section
    nxt = NEXT_SECTION.search(rest)
    if nxt:
        rest = rest[: nxt.start()]
    # Supprimer la ponctuation parasite en début et normaliser les espaces
    content = _LEADING_PUNCT.sub("", rest)
    content = re.sub(r"\s+", " ", content).strip()
    if not content:
        return ""
    # Tronquer proprement à la dernière phrase complète
    if len(content) > max_chars:
        cut = content[:max_chars]
        last_dot = cut.rfind(".")
        content = cut[: last_dot + 1] if last_dot > 50 else cut.rstrip() + "…"
    return content


def _clean_keywords(kw_str: str) -> list[str]:
    """Parse et déduplique les mots-clés CSV."""
    kws: list[str] = []
    seen: set[str] = set()
    for kw in kw_str.split(","):
        kw = kw.strip().lower()
        if kw and kw not in seen:
            seen.add(kw)
            kws.append(kw)
        if len(kws) >= MAX_KEYWORDS:
            break
    return kws


def _slugify(s: str) -> str:
    """Convertit une chaîne en slug ASCII pour les doc_id."""
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode()
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    return re.sub(r"[\s/\\-]+", "_", s)[:40]


def build_text(
    specialty: str,
    case_name: str,
    description: str,
    hpi: str,
    assessment: str,
    keywords: list[str],
) -> str:
    """Assemble le texte vectorisable pour l'embedding."""
    parts: list[str] = [
        f"Clinical case — {specialty}.",
        f"Case: {case_name}.",
    ]
    if description.strip():
        desc = description.strip().rstrip(".")
        parts.append(f"Presentation: {desc}.")
    if hpi:
        hpi_clean = hpi.rstrip(".")
        parts.append(f"History: {hpi_clean}.")
    if assessment:
        assess_clean = assessment.rstrip(".")
        parts.append(f"Assessment: {assess_clean}.")
    if keywords:
        parts.append("Keywords: " + ", ".join(keywords) + ".")
    return " ".join(parts)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase D — mtsamples")
    parser.add_argument("--input",  required=True, help="Chemin vers mtsamples.csv")
    parser.add_argument("--output", required=True, help="Répertoire de sortie")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "mtsamples_clinical_cases.jsonl"

    total = 0
    skipped_empty = 0
    docs_written = 0
    specialty_counts: dict[str, int] = {}

    with open(args.input, encoding="utf-8", newline="") as in_f, \
         open(out_path, "w", encoding="utf-8") as out_f:

        reader = csv.DictReader(in_f)
        for row in reader:
            total += 1
            transcription = row.get("transcription", "").strip()
            if not transcription:
                skipped_empty += 1
                continue

            specialty  = row.get("medical_specialty", "").strip()
            case_name  = row.get("sample_name", "").strip()
            description = row.get("description", "").strip()
            kw_raw     = row.get("keywords", "")

            # Extraction des sections clés
            assessment = _extract_section(transcription, ASSESSMENT_HEADERS, MAX_ASSESSMENT_CHARS)
            hpi        = _extract_section(transcription, HPI_HEADERS, MAX_HPI_CHARS)
            keywords   = _clean_keywords(kw_raw)

            # Texte vectorisable
            text = build_text(specialty, case_name, description, hpi, assessment, keywords)

            slug_sp  = _slugify(specialty)
            doc_id   = f"clinical_{slug_sp}_{docs_written:04d}"

            doc = {
                "doc_id":      doc_id,
                "specialty":   specialty,
                "case_name":   case_name,
                "description": description,
                "assessment":  assessment,
                "hpi":         hpi,
                "keywords":    keywords,
                "text":        text,
            }
            out_f.write(json.dumps(doc, ensure_ascii=False) + "\n")
            docs_written += 1
            specialty_counts[specialty] = specialty_counts.get(specialty, 0) + 1

    logger.info("")
    logger.info("=" * 52)
    logger.info(f"  Lignes lues           : {total:,}")
    logger.info(f"  Sans transcription    : {skipped_empty}")
    logger.info(f"  Documents produits    : {docs_written:,}")
    logger.info(f"  Spécialités           : {len(specialty_counts)}")
    logger.info(f"  Avec ASSESSMENT extrait : "
                f"{sum(1 for _ in open(out_path, encoding='utf-8') if '\"assessment\": \"\"' not in _)}")
    logger.info(f"  Fichier               : {out_path}")
    logger.info("=" * 52)
    logger.info("")
    logger.info("Top 10 spécialités :")
    for sp, n in sorted(specialty_counts.items(), key=lambda x: -x[1])[:10]:
        logger.info(f"    {n:4d}  {sp}")


if __name__ == "__main__":
    main()
