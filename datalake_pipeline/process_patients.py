#!/usr/bin/env python3
"""
Phase C — Extraction et description des patients DDXPlus.

Produit processed/ddxplus_patient_descriptions.jsonl :
  50 patients/pathologie, sélectionnés de façon à couvrir les 8 strates
  (4 tranches d'âge × 2 sexes) pour maximiser la diversité démographique.
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import logging
import random
from collections import defaultdict
from pathlib import Path
from typing import NamedTuple

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Paramètres ────────────────────────────────────────────────────────────────

PATIENTS_PER_PATHO = 50
RESERVOIR_PER_STRATUM = 30
SEED = 42

AGE_STRATA: list[tuple[int, int, str]] = [
    (0,  17,  "enfant_ado"),
    (18, 39,  "jeune_adulte"),
    (40, 64,  "adulte"),
    (65, 150, "senior"),
]
AGE_STRATA_FR: dict[str, str] = {
    "enfant_ado":    "enfant ou adolescent",
    "jeune_adulte":  "jeune adulte",
    "adulte":        "adulte",
    "senior":        "personne âgée",
}
SEX_FR: dict[str, str] = {"M": "homme", "F": "femme"}

# ── Labels courts pour codes binaires (208 codes B) ───────────────────────────
# Clé : code E_xx  |  Valeur : label français court (présence = oui)

EVIDENCE_LABELS: dict[str, str] = {
    # ── Symptômes (SYMPTOME) ──────────────────────────────────────────────────
    "E_9":   "Adénopathies (ganglions enflés/douloureux)",
    "E_13":  "Aggravation progressive depuis 2 semaines",
    "E_14":  "Douleurs thoraciques au repos",
    "E_23":  "Apnées du sommeil",
    "E_30":  "Ballonnement abdominal",
    "E_32":  "Diminution de l'appétit / des boires",
    "E_33":  "Douleur soulagée en se penchant en avant",
    "E_38":  "Douleurs à la mâchoire",
    "E_39":  "Confusion",
    "E_42":  "Contact avec un allergène",
    "E_43":  "Convulsions / perte de conscience",
    "E_45":  "Hémoptysie (crachats sanglants)",
    "E_50":  "Sueurs importantes",
    "E_51":  "Diarrhées",
    "E_52":  "Diplopie (vision double)",
    "E_53":  "Douleur",
    "E_63":  "Dysarthrie (difficulté à articuler)",
    "E_64":  "Dyspnée d'effort",
    "E_65":  "Dysphagie (difficulté à avaler)",
    "E_66":  "Dyspnée (essoufflement important)",
    "E_67":  "Crises de suffocation nocturnes",
    "E_74":  "Yeux rouges (hyperhémie conjonctivale)",
    "E_75":  "Sensation d'étouffement",
    "E_76":  "Étourdissements légers / déséquilibre",
    "E_77":  "Crachats colorés ou abondants",
    "E_82":  "Faiblesse et étourdissements",
    "E_83":  "Faiblesse musculaire faciale / oculaire",
    "E_84":  "Faiblesse des 4 membres",
    "E_88":  "Incapacité fonctionnelle (alitement)",
    "E_89":  "Fatigue constante / sommeil non réparateur",
    "E_90":  "Faiblesse musculaire aggravée par la fatigue",
    "E_91":  "Fièvre",
    "E_92":  "Rougeur soudaine des joues (flush)",
    "E_93":  "Engourdissements dans les pieds",
    "E_94":  "Frissons",
    "E_96":  "Prise de poids récente",
    "E_97":  "Mal de gorge",
    "E_103": "Anosmie (perte d'odorat)",
    "E_111": "Sentiment de mort imminente",
    "E_112": "Wheezing post-toux (inspiration sifflante)",
    "E_114": "Irritabilité / humeur changeante",
    "E_127": "Larmoiement excessif",
    "E_128": "Épisode bref d'étouffement",
    "E_129": "Lésions cutanées",
    "E_140": "Méléna (selles noires)",
    "E_144": "Douleurs musculaires diffuses",
    "E_145": "Ménorragies (menstruations abondantes)",
    "E_148": "Nausées",
    "E_150": "Transit intestinal conservé (selles et gaz)",
    "E_151": "Œdème",
    "E_154": "Pâleur",
    "E_155": "Palpitations",
    "E_156": "Faiblesse ou paralysie faciale",
    "E_157": "Paresthésies (mains, pieds, bouche)",
    "E_159": "Syncope (perte de conscience)",
    "E_161": "Perte d'appétit",
    "E_162": "Perte de poids involontaire",
    "E_163": "Pertes vaginales",
    "E_164": "Arythmie cardiaque perçue",
    "E_166": "Vomissements après toux",
    "E_168": "Difficulté à contrôler la langue",
    "E_169": "Prurit nasal / palatin",
    "E_170": "Prurit oculaire (démangeaisons des yeux)",
    "E_171": "Déréalisation / dépersonnalisation",
    "E_172": "Ptosis (difficulté à lever les paupières)",
    "E_173": "Pyrosis (brûlures remontantes)",
    "E_174": "Perte de poids et d'appétit",
    "E_175": "Altération de l'état général",
    "E_176": "Déficit moteur focal (membres/visage)",
    "E_177": "Paresthésies généralisées",
    "E_178": "Saignements ou ecchymoses inhabituels",
    "E_179": "Rectorragie (sang rouge dans les selles)",
    "E_180": "Paralysie du regard",
    "E_181": "Rhinorrhée claire (nez qui coule)",
    "E_182": "Rhinorrhée purulente (écoulement coloré)",
    "E_188": "Ictère (selles pâles, urines foncées)",
    "E_190": "Hypersalivation",
    "E_192": "Contractures cervicales",
    "E_193": "Spasmes musculaires faciaux / cervicaux",
    "E_194": "Stridor inspiratoire",
    "E_201": "Toux",
    "E_202": "Toux aboyante",
    "E_203": "Quintes de toux intenses",
    "E_205": "Trismus (difficulté à ouvrir la bouche)",
    "E_206": "Ulcères buccaux",
    "E_210": "Hématémèse (sang dans vomissements)",
    "E_211": "Vomissements",
    "E_212": "Dysphonie (voix modifiée)",
    "E_214": "Wheezing (sifflements expiratoires)",
    "E_215": "Symptômes post-prandiaux (pires après repas)",
    "E_216": "Douleur mécanique (pire aux mouvements)",
    "E_217": "Symptômes aggravés en décubitus",
    "E_218": "Symptômes à l'effort, soulagés au repos",
    "E_219": "Symptômes nocturnes",
    "E_220": "Douleur pleurale (pire à l'inspiration)",
    "E_221": "Douleur à la toux ou à l'effort",
    # ── Antécédents (ANTECEDENT) ──────────────────────────────────────────────
    "E_0":   "Infection virale récente",
    "E_1":   "Antibiotiques récents (otite)",
    "E_2":   "VIH séropositif",
    "E_3":   "Antécédent de péricardite",
    "E_4":   "Antécédent familial de croup",
    "E_5":   "Antécédent d'OAP",
    "E_6":   "Pancréatite chronique",
    "E_7":   "Malnutrition",
    "E_8":   "Insuffisance rénale dialysée",
    "E_10":  "AINS récents",
    "E_11":  "Allaitement prolongé (> 9 mois)",
    "E_12":  "Allergie alimentaire sévère",
    "E_15":  "Antipsychotique récent (< 7 jours)",
    "E_16":  "Anxiété / fébrilité de fond",
    "E_17":  "Origines asiatiques",
    "E_18":  "Fibrose kystique",
    "E_19":  "Hyperthyroïdie connue",
    "E_20":  "Polyarthrite rhumatoïde",
    "E_21":  "Antécédent de pneumothorax spontané",
    "E_22":  "Valvulopathie connue",
    "E_24":  "Antécédent d'anémie",
    "E_25":  "Antécédent familial de céphalée en grappe",
    "E_26":  "Antécédent familial d'anémie",
    "E_27":  "Antécédent d'IST",
    "E_28":  "Antécédent familial de myasthénie",
    "E_29":  "Antécédent familial psychiatrique",
    "E_31":  "BPCO sévère",
    "E_34":  "Cancer actif",
    "E_35":  "Consommation régulière de caféine",
    "E_37":  "Cancer métastatique",
    "E_40":  "Contact avec un cas de coqueluche",
    "E_41":  "Contact récent avec personne symptomatique",
    "E_44":  "Corticothérapie en cours",
    "E_46":  "≥ 2 crises d'asthme dans l'année",
    "E_47":  "Maladie de Crohn ou colite ulcéreuse",
    "E_48":  "Cohabitation avec ≥ 4 personnes",
    "E_49":  "Fréquente ou travaille en garderie",
    "E_60":  "Consommation de boissons énergisantes",
    "E_61":  "Toxicomanie intraveineuse",
    "E_62":  "Usage de drogues stimulantes",
    "E_69":  "Diabète",
    "E_70":  "Obésité morbide (IMC ≥ 40)",
    "E_71":  "Hypercholestérolémie",
    "E_72":  "Exacerbation(s) de BPCO dans l'année",
    "E_73":  "Contact avec un cas d'Ebola",
    "E_78":  "Alcoolisme",
    "E_79":  "Tabagisme actif",
    "E_80":  "Antécédent de dépression",
    "E_81":  "Anxiété chronique",
    "E_86":  "Antécédent familial d'allergies",
    "E_87":  "Antécédent familial d'asthme",
    "E_95":  "Maladie de Parkinson",
    "E_98":  "Hernie hiatale",
    "E_99":  "Migraines (personnel ou familial)",
    "E_100": "Traitement hormonal",
    "E_101": "Hospitalisation pour asthme dans l'année",
    "E_102": "Hypertension artérielle",
    "E_104": "Hypertension artérielle traitée",
    "E_105": "Antécédent d'infarctus ou d'angine",
    "E_106": "Insuffisance cardiaque",
    "E_107": "Antécédent d'AVC",
    "E_108": "Artériopathie périphérique",
    "E_109": "Antécédent de TVP",
    "E_110": "Immobilisation > 3 jours dans le mois",
    "E_113": "Insuffisance rénale chronique",
    "E_115": "Rapports non protégés avec partenaires multiples",
    "E_116": "Rhume récent (< 2 semaines)",
    "E_118": "Antécédent de pneumonie",
    "E_119": "Sinusite chronique",
    "E_120": "Polypes nasaux",
    "E_121": "Déviation du septum nasal",
    "E_123": "BPCO",
    "E_124": "Asthme",
    "E_125": "Reflux gastro-œsophagien (antécédent)",
    "E_126": "Cirrhose hépatique",
    "E_137": "Exérèse ganglionnaire antérieure",
    "E_138": "Fibromyalgie",
    "E_139": "Malformation cardiaque congénitale",
    "E_141": "Ménarche précoce (< 12 ans)",
    "E_142": "Mère asthmatique",
    "E_143": "Activité physique régulière (≥ 4×/semaine)",
    "E_146": "Anticoagulants oraux (NACOs)",
    "E_147": "Traitement antipsychotique IV/IM récent",
    "E_149": "Inhibiteurs calciques en cours",
    "E_153": "Traitement de l'ostéoporose",
    "E_158": "Maladie endocrinienne",
    "E_160": "Naissance prématurée ou complications néonatales",
    "E_165": "Antécédent familial de pneumothorax",
    "E_167": "Grossesse",
    "E_183": "Résidence rurale",
    "E_184": "Vasodilatateur en cours",
    "E_185": "Antécédent de traumatisme crânien",
    "E_186": "Syndrome d'apnées du sommeil (SAHOS)",
    "E_187": "Consommation récente de poisson gras ou fromage",
    "E_189": "Partenaire séropositif VIH",
    "E_191": "Ex-fumeur",
    "E_195": "Résidence en banlieue",
    "E_196": "Chirurgie récente (< 1 mois)",
    "E_197": "Syndrome néphrotique (protéinurie)",
    "E_198": "Travailleur agricole",
    "E_199": "Travailleur du bâtiment",
    "E_200": "Travailleur minier",
    "E_207": "Résidence en ville",
    "E_208": "Maigreur (IMC < 18.5)",
    "E_209": "Vaccins à jour",
    "E_213": "Décongestionnants ou stimulants récents",
    "E_222": "Exposition à la fumée secondaire",
    "E_223": "Antécédent familial de cancer du pancréas",
    "E_224": "Antécédent familial de cancer du poumon",
    "E_225": "Antécédent familial de maladie CV précoce",
    "E_226": "Terrain atopique",
    "E_227": "Immunosuppression",
}

# ── Préfixes courts pour codes multichoix (data_type M) ──────────────────────

MULTICHOICE_PREFIXES: dict[str, str] = {
    "E_54":  "Type de douleur",
    "E_55":  "Douleur localisée au",
    "E_57":  "Irradiation vers",
    "E_133": "Lésion cutanée au niveau de",
    "E_152": "Œdème au niveau de",
    "E_204": "Voyage récent en",
}

# Codes C-type à réponse booléenne (valeur positive = oui → label du fait)
C_BOOL_LABELS: dict[str, str] = {
    "E_131": "Lésions desquamatives (pèlent)",
    "E_132": "Lésions cutanées surélevées",
    "E_135": "Lésions cutanées > 1 cm",
}

# ── Labels pour codes catégoriels numériques (data_type C, valeurs 0–5) ──────

C_NUMERIC_LABELS: dict[str, dict[str, str]] = {
    "E_56": {  # intensité douleur
        "1": "Intensité douleur faible (1/5)",
        "2": "Intensité douleur modérée (2/5)",
        "3": "Intensité douleur modérée-sévère (3/5)",
        "4": "Intensité douleur sévère (4/5)",
        "5": "Intensité douleur très sévère (5/5)",
    },
    "E_58": {  # précision localisation douleur
        "1": "Douleur peu précisément localisée (1/5)",
        "2": "Douleur assez localisée (2/5)",
        "3": "Douleur modérément localisée (3/5)",
        "4": "Douleur bien localisée (4/5)",
        "5": "Douleur très précisément localisée (5/5)",
    },
    "E_59": {  # vitesse apparition douleur
        "1": "Douleur d'apparition très lente",
        "2": "Douleur d'apparition lente",
        "3": "Douleur d'apparition progressive",
        "4": "Douleur d'apparition rapide",
        "5": "Douleur d'apparition soudaine",
    },
    "E_134": {  # intensité douleur lésions
        "1": "Douleur des lésions faible (1/5)",
        "2": "Douleur des lésions modérée (2/5)",
        "3": "Douleur des lésions modérée-sévère (3/5)",
        "4": "Douleur des lésions sévère (4/5)",
        "5": "Douleur des lésions très sévère (5/5)",
    },
    "E_136": {  # intensité démangeaisons
        "1": "Démangeaisons légères (1/5)",
        "2": "Démangeaisons modérées (2/5)",
        "3": "Démangeaisons importantes (3/5)",
        "4": "Démangeaisons sévères (4/5)",
        "5": "Démangeaisons intolérables (5/5)",
    },
}

# ── Structures de données ─────────────────────────────────────────────────────

class PatientRow(NamedTuple):
    age: int
    sex: str
    pathology_en: str
    evidences: list[str]
    diff_diag: list[tuple[str, float]]
    initial_evidence: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def age_stratum(age: int) -> str:
    for lo, hi, label in AGE_STRATA:
        if lo <= age <= hi:
            return label
    return "adulte"


def parse_row(row: list[str]) -> PatientRow | None:
    try:
        age = int(row[0])
        diff_diag_raw = ast.literal_eval(row[1])
        diff_diag: list[tuple[str, float]] = [
            (str(d[0]), float(d[1])) for d in diff_diag_raw
        ]
        sex = row[2].strip()
        pathology_en = row[3].strip()
        evidences: list[str] = ast.literal_eval(row[4])
        initial_evidence = row[5].strip()
        return PatientRow(age, sex, pathology_en, evidences, diff_diag, initial_evidence)
    except Exception:
        return None


def _ucfirst(s: str) -> str:
    """Capitalise uniquement la 1ère lettre, préserve le reste (ex. AVC → AVC)."""
    return (s[0].upper() + s[1:]) if s else s


def decode_evidence(code: str, evidences_db: dict) -> tuple[str, bool]:
    """
    Retourne (label_fr, is_antecedent).
    Retourne ("", ...) pour les valeurs par défaut/nulles.
    Priorité : EVIDENCE_LABELS / C_BOOL_LABELS > MULTICHOICE_PREFIXES > question_fr brute.
    """
    if "_@_" in code:
        base, value = code.split("_@_", 1)
        ev = evidences_db.get(base, {})
        is_ant = bool(ev.get("is_antecedent", False))

        # Valeur par défaut → ignorer
        default = ev.get("default_value", "")
        if str(value) == str(default):
            return "", is_ant

        # Codes avec value_meaning (M-type et C-type avec V_xxx)
        val_meaning = ev.get("value_meaning", {}).get(value, {})
        if val_meaning:
            val_fr = val_meaning.get("fr", "")
            if not val_fr or val_fr.upper() == "NA":
                return "", is_ant
            # Valeur booléenne encodée "O"/"N"
            if val_fr.upper() in ("O", "Y", "OUI", "YES"):
                label = C_BOOL_LABELS.get(base, EVIDENCE_LABELS.get(base, ""))
                if not label:
                    label = ev.get("question_fr", base).rstrip("?").strip()
                return _ucfirst(label), is_ant
            if val_fr.upper() in ("N", "NO", "NON"):
                return "", is_ant
            prefix = MULTICHOICE_PREFIXES.get(base, ev.get("question_fr", base).rstrip("?:").strip())
            return f"{prefix} : {val_fr}", is_ant

        # C-type numérique (E_56, E_58, E_59…)
        if base in C_NUMERIC_LABELS:
            label = C_NUMERIC_LABELS[base].get(str(value), "")
            return label, is_ant

        # C-type booléen avec valeur entière 1 (E_131, E_132, E_135)
        if str(value) in ("1", "True"):
            label = C_BOOL_LABELS.get(base, EVIDENCE_LABELS.get(base, ""))
            if not label:
                label = ev.get("question_fr", base).rstrip("?").strip()
            return _ucfirst(label), is_ant

        return "", is_ant

    else:
        ev = evidences_db.get(code, {})
        is_ant = bool(ev.get("is_antecedent", False))
        label = EVIDENCE_LABELS.get(code, "")
        if not label:
            label = ev.get("question_fr", code.replace("_", " ")).rstrip("?").strip()
        return _ucfirst(label) if label else "", is_ant


def build_patient_text(
    patient: PatientRow,
    pathology_fr: str,
    en_to_fr: dict[str, str],
    evidences_db: dict,
) -> tuple[str, list[str], list[str]]:
    """
    Construit le texte descriptif du patient.
    Retourne (text, symptoms_list, antecedents_list).
    """
    # Motif d'entrée
    initial_label, _ = decode_evidence(patient.initial_evidence, evidences_db)
    if not initial_label:
        initial_label = patient.initial_evidence

    # Décodage de toutes les évidences
    symptoms: list[str] = []
    antecedents: list[str] = []
    seen: set[str] = set()
    for code in patient.evidences:
        label, is_ant = decode_evidence(code, evidences_db)
        if not label or label in seen:
            continue
        seen.add(label)
        if is_ant:
            antecedents.append(label)
        else:
            symptoms.append(label)

    # Diagnostics différentiels (top 5, ≥ 5%, hors diagnostic principal)
    diff_diag_fr: list[tuple[str, int]] = []
    for en_name, prob in patient.diff_diag:
        if prob < 0.05:
            continue
        fr_name = en_to_fr.get(en_name, en_name)
        if fr_name == pathology_fr:
            continue
        diff_diag_fr.append((fr_name, round(prob * 100)))
        if len(diff_diag_fr) >= 5:
            break

    age_grp_fr = AGE_STRATA_FR.get(age_stratum(patient.age), "adulte")
    sex_fr = SEX_FR.get(patient.sex, patient.sex)

    parts: list[str] = [
        f"Patient de {patient.age} ans ({sex_fr}, {age_grp_fr}).",
        f"Motif d'entrée : {initial_label}.",
    ]
    if symptoms:
        parts.append("Symptômes : " + " ; ".join(symptoms) + ".")
    if antecedents:
        parts.append("Antécédents : " + " ; ".join(antecedents) + ".")
    parts.append(f"Diagnostic retenu : {pathology_fr}.")
    if diff_diag_fr:
        dd_str = " ; ".join(f"{n} ({p}%)" for n, p in diff_diag_fr)
        parts.append(f"Diagnostics différentiels : {dd_str}.")

    return " ".join(parts), symptoms, antecedents


# ── Reservoir sampling ────────────────────────────────────────────────────────

class ReservoirSampler:
    """Algorithme R : garde un sous-ensemble aléatoire d'un flux."""

    def __init__(self, size: int, rng: random.Random) -> None:
        self._size = size
        self._rng = rng
        self._pool: list = []
        self._n = 0

    def add(self, item) -> None:
        self._n += 1
        if len(self._pool) < self._size:
            self._pool.append(item)
        else:
            j = self._rng.randint(0, self._n - 1)
            if j < self._size:
                self._pool[j] = item

    def pool(self) -> list:
        return list(self._pool)


# ── Sélection diversifiée ─────────────────────────────────────────────────────

def select_diverse(
    strata: dict[tuple[str, str], list[PatientRow]],
    n: int,
    rng: random.Random,
) -> list[PatientRow]:
    """
    Sélectionne n patients en maximisant la couverture des strates.
    Allocation round-robin avec backfill si une strate est sous-peuplée.
    """
    non_empty = {k: list(v) for k, v in strata.items() if v}
    if not non_empty:
        return []

    strata_sorted = sorted(non_empty.items(), key=lambda x: len(x[1]))
    num_strata = len(strata_sorted)
    base = n // num_strata
    remainder = n % num_strata

    selected: list[PatientRow] = []
    leftover_pool: list[PatientRow] = []

    for i, (key, pool) in enumerate(strata_sorted):
        quota = base + (1 if i < remainder else 0)
        drawn = rng.sample(pool, min(quota, len(pool)))
        selected.extend(drawn)
        drawn_ids = {id(p) for p in drawn}
        leftover_pool.extend(p for p in pool if id(p) not in drawn_ids)

    deficit = n - len(selected)
    if deficit > 0 and leftover_pool:
        extra = rng.sample(leftover_pool, min(deficit, len(leftover_pool)))
        selected.extend(extra)

    return selected


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase C — patients DDXPlus")
    parser.add_argument("--patients",   required=True, help="CSV patients DDXPlus")
    parser.add_argument("--conditions", required=True, help="release_conditions.json")
    parser.add_argument("--evidences",  required=True, help="release_evidences.json")
    parser.add_argument("--output",     required=True, help="Répertoire de sortie")
    parser.add_argument("--n",    type=int, default=PATIENTS_PER_PATHO)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    output_dir = Path(args.output)

    # ── Données de référence ─────────────────────────────────────────────────
    logger.info("Chargement des données de référence…")
    with open(args.conditions, encoding="utf-8") as f:
        conditions: dict = json.load(f)
    with open(args.evidences, encoding="utf-8") as f:
        evidences_db: dict = json.load(f)

    en_to_fr: dict[str, str] = {
        v.get("cond-name-eng", ""): k
        for k, v in conditions.items()
        if v.get("cond-name-eng")
    }
    logger.info(f"  {len(conditions)} pathologies, {len(evidences_db)} évidences")

    # ── Reservoir sampling sur le CSV ────────────────────────────────────────
    logger.info("Lecture du CSV patients (reservoir sampling)…")

    reservoirs: dict[str, dict[tuple[str, str], ReservoirSampler]] = defaultdict(
        lambda: defaultdict(lambda: ReservoirSampler(RESERVOIR_PER_STRATUM, rng))
    )

    total_rows = 0
    with open(args.patients, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for raw_row in reader:
            total_rows += 1
            patient = parse_row(raw_row)
            if patient is None:
                continue
            stratum_key = (age_stratum(patient.age), patient.sex)
            reservoirs[patient.pathology_en][stratum_key].add(patient)

    logger.info(f"  {total_rows:,} patients lus, {len(reservoirs)} pathologies")

    # ── Production des documents ─────────────────────────────────────────────
    logger.info("Production des documents patients…")
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "ddxplus_patient_descriptions.jsonl"

    total_docs = 0
    unknown: list[str] = []

    with open(out_path, "w", encoding="utf-8") as out_f:
        for patho_en in sorted(reservoirs):
            patho_fr = en_to_fr.get(patho_en)
            if not patho_fr:
                unknown.append(patho_en)
                logger.warning(f"  Pathologie inconnue : {patho_en!r}")
                continue

            strata: dict[tuple[str, str], list[PatientRow]] = {
                k: v.pool() for k, v in reservoirs[patho_en].items()
            }
            selected = select_diverse(strata, args.n, rng)

            patho_info = conditions[patho_fr]
            icd10 = ", ".join(patho_info.get("icd10-id", []))

            for idx, patient in enumerate(selected):
                text, symptoms, antecedents = build_patient_text(
                    patient, patho_fr, en_to_fr, evidences_db
                )
                safe_name = (
                    patho_fr.replace(" ", "_")
                             .replace("/", "_")
                             .replace("(", "")
                             .replace(")", "")
                )
                doc = {
                    "doc_id": f"patient_{safe_name}_{idx:04d}",
                    "pathology_fr": patho_fr,
                    "pathology_en": patho_en,
                    "icd10": icd10,
                    "age": patient.age,
                    "sex": patient.sex,
                    "age_group": age_stratum(patient.age),
                    "symptoms": symptoms,
                    "antecedents": antecedents,
                    "differential_diagnosis": [
                        {"pathology_fr": en_to_fr.get(en, en), "probability": round(p, 4)}
                        for en, p in patient.diff_diag[:8]
                    ],
                    "text": text,
                }
                out_f.write(json.dumps(doc, ensure_ascii=False) + "\n")
                total_docs += 1

            num_strata = len([v for v in strata.values() if v])
            logger.info(
                f"  [{total_docs - len(selected) + 1:>5}/{total_docs:>5}] "
                f"{patho_fr}: {len(selected)} patients, {num_strata} strates"
            )

    logger.info("")
    logger.info("=" * 52)
    logger.info(f"  Documents produits   : {total_docs:,}")
    logger.info(f"  Pathologies traitées : {len(reservoirs) - len(unknown)}/49")
    if unknown:
        logger.warning(f"  Pathologies inconnues: {unknown}")
    logger.info(f"  Fichier              : {out_path}")
    logger.info("=" * 52)


if __name__ == "__main__":
    main()
