"""
=============================================================================
Pipeline unifie de Data Processing - Projet M2 RAG Medical
=============================================================================

Traite les 3 sources de donnees en un seul pipeline :
  1. DDXPlus FR    -> documents de pathologies + descriptions patients (JSONL)
  2. FINESS        -> centres de sante normalises (JSONL pour MongoDB)
  3. CSV symptomes -> descriptions nettoyees et deduplicees (JSONL)

Produit une sortie homogene dans processed/ prete pour :
  - Vectorisation (EmbeddingManager -> pgvector)
  - Import MongoDB (centres de sante geolocalisees)
  - Evaluation du retriever

Usage :
  python unified_data_processor.py \
    --ddxplus-conditions  raw/ddxplus/release_conditions.json \
    --ddxplus-evidences   raw/ddxplus/release_evidences.json \
    --ddxplus-patients    raw/ddxplus/release_train_patients.csv \
    --finess-etab         raw/finess/finess_etablissements.csv \
    --finess-geo          raw/finess/finess_geolocalisation.csv \
    --csv-symptoms        raw/symptom_csv/combined_medical_data.csv \
    --output-dir          ./processed \
    --max-patients        100000

Prerequis :
  pip install pyproj --break-system-packages
"""

import os
import json
import csv
import math
import argparse
import logging
import hashlib
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter, defaultdict
from typing import Optional
from dataclasses import dataclass, field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ===================================================================
# DATA CLASSES
# ===================================================================


@dataclass
class Evidence:
    name: str
    question_fr: str
    question_en: str
    is_antecedent: bool
    data_type: str
    default_value: str
    possible_values: list = field(default_factory=list)
    value_meaning: dict = field(default_factory=dict)


@dataclass
class Pathology:
    condition_name: str
    name_fr: str
    name_en: str
    icd10_id: str
    severity: int
    symptoms: list = field(default_factory=list)
    antecedents: list = field(default_factory=list)


@dataclass
class Patient:
    age: int
    sex: str
    pathology: str
    evidences: list = field(default_factory=list)
    differential_diagnosis: list = field(default_factory=list)
    initial_evidence: str = ""


@dataclass
class HealthCenter:
    finess_id: str
    name: str
    name_long: str
    address: str
    postal_code: str
    city: str
    department: str
    department_name: str
    phone: str
    category_code: str
    category_label: str
    aggregate_category: str
    aggregate_label: str
    specialty_code: str
    specialty_label: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


# ===================================================================
# 1. DDXPlus PROCESSOR
# ===================================================================


class EvidenceRegistry:
    """Indexe les 223 evidences DDXPlus et convertit les codes en texte FR."""

    def __init__(self, path: str):
        self.evidences: dict[str, Evidence] = {}
        self._load(path)

    def _load(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for name, d in raw.items():
            self.evidences[name] = Evidence(
                name=name,
                question_fr=d.get("question_fr", ""),
                question_en=d.get("question_en", ""),
                is_antecedent=d.get("is_antecedent", False),
                data_type=d.get("data_type", "B"),
                default_value=d.get("default_value", ""),
                possible_values=d.get("possible-values", []),
                value_meaning=d.get("value_meaning", {}),
            )
        n_sym = sum(1 for e in self.evidences.values() if not e.is_antecedent)
        n_ant = sum(1 for e in self.evidences.values() if e.is_antecedent)
        logger.info(f"  EvidenceRegistry : {len(self.evidences)} evidences ({n_sym} symptomes, {n_ant} antecedents)")

    def get(self, name: str) -> Optional[Evidence]:
        return self.evidences.get(name)

    def code_to_text(self, code: str) -> str:
        """Convertit un code evidence en texte FR naturel."""
        if "_@_" in code:
            evi_name, evi_value = code.split("_@_", 1)
        else:
            evi_name, evi_value = code, None

        evi = self.get(evi_name)
        if evi is None:
            clean = evi_name.replace("_", " ").replace(".", " ")
            return f"{clean} : {evi_value.replace('_', ' ')}" if evi_value else clean

        question = evi.question_fr.rstrip("?").strip()

        if evi.data_type == "B":
            return self._question_to_statement(question, evi.name)

        if evi.data_type in ("C", "M") and evi_value is not None:
            meaning = self._value_meaning_fr(evi, evi_value)
            if meaning and meaning.lower() not in ("na", "n/a", ""):
                return f"{question} : {meaning}"
            return f"{question} : {evi_value.replace('_', ' ')}"

        return question

    def _question_to_statement(self, q: str, name: str) -> str:
        ql = q.lower().strip()
        articles = ["de la ", "du ", "de l'", "des ", "de ", "le ", "la ", "l'", "un ", "une "]

        def strip_articles(s):
            for a in articles:
                if s.startswith(a):
                    return s[len(a):]
            return s

        if ql.startswith("avez-vous") or ql.startswith("avez vous"):
            r = re.sub(r"^avez[- ]vous\s*", "", ql)
            r = strip_articles(r)
            if r.startswith("mal "):
                r = "douleur " + r[4:]
            return r.strip().capitalize()

        if ql.startswith("ressentez-vous"):
            r = ql.replace("ressentez-vous", "", 1).strip()
            return strip_articles(r).strip().capitalize()

        if ql.startswith("souffrez-vous"):
            r = ql.replace("souffrez-vous", "", 1).strip()
            return strip_articles(r).strip().capitalize()

        if "transpirez" in ql:
            return "Transpiration excessive"
        if "fumeur" in ql:
            return "Tabagisme"
        if ql.startswith("êtes-vous"):
            r = ql.replace("êtes-vous", "", 1).strip()
            return strip_articles(r).strip().capitalize()
        if ql.startswith("vivez-vous"):
            return ql.replace("vivez-vous", "Vit", 1).strip().capitalize()

        return q.capitalize() if len(q) > 3 else name.replace("_", " ").capitalize()

    def _value_meaning_fr(self, evi: Evidence, val: str) -> str:
        if val in evi.value_meaning:
            m = evi.value_meaning[val]
            return m.get("fr", str(m)) if isinstance(m, dict) else str(m)
        return val

    def export_lookup(self, path: str) -> None:
        lookup = {}
        for name, e in self.evidences.items():
            entry = {"question_fr": e.question_fr, "is_antecedent": e.is_antecedent, "type": e.data_type}
            if e.value_meaning:
                entry["values_fr"] = {
                    k: (v.get("fr", str(v)) if isinstance(v, dict) else str(v))
                    for k, v in e.value_meaning.items()
                }
            lookup[name] = entry
        with open(path, "w", encoding="utf-8") as f:
            json.dump(lookup, f, ensure_ascii=False, indent=2)


class DDXPlusProcessor:
    """Transforme DDXPlus brut en documents JSONL pour le RAG."""

    def __init__(self, conditions_path: str, evidences_path: str, patients_path: str, max_patients: Optional[int] = None):
        self.evi_registry = EvidenceRegistry(evidences_path)
        self.pathologies: dict[str, Pathology] = {}
        self.patients_path = patients_path
        self.max_patients = max_patients
        self._load_conditions(conditions_path)

    def _load_conditions(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for name, d in raw.items():
            self.pathologies[name] = Pathology(
                condition_name=name,
                name_fr=d.get("cond-name-fr", name),
                name_en=d.get("cond-name-eng", name),
                icd10_id=d.get("icd10-id", ""),
                severity=d.get("severity", 0),
                symptoms=list(d.get("symptoms", {}).keys()),
                antecedents=list(d.get("antecedents", {}).keys()),
            )
        logger.info(f"  DDXPlus : {len(self.pathologies)} pathologies chargees")

    def process(self, output_dir: Path) -> dict:
        """Execute le traitement complet DDXPlus."""
        logger.info("=" * 60)
        logger.info("[1/3] Traitement DDXPlus")
        logger.info("=" * 60)

        stats = {"source": "ddxplus"}

        # 1a. Documents de pathologies (pour le RAG retriever)
        patho_docs = self._build_pathology_docs()
        patho_path = output_dir / "ddxplus_pathology_documents.jsonl"
        self._write_jsonl(patho_docs, patho_path)
        stats["pathology_documents"] = len(patho_docs)
        logger.info(f"  -> {len(patho_docs)} documents de pathologies")

        # 1b. Descriptions de patients (pour le RAG retriever + evaluation)
        patient_docs, patho_dist = self._build_patient_docs()
        patients_path = output_dir / "ddxplus_patient_descriptions.jsonl"
        self._write_jsonl(patient_docs, patients_path)
        stats["patient_descriptions"] = len(patient_docs)
        stats["pathology_distribution"] = dict(Counter(patho_dist).most_common(10))

        if patient_docs:
            lengths = [len(d["text"]) for d in patient_docs]
            stats["avg_text_length"] = round(sum(lengths) / len(lengths))
        logger.info(f"  -> {len(patient_docs)} descriptions de patients")

        # 1c. Table de correspondance
        self.evi_registry.export_lookup(str(output_dir / "ddxplus_evidence_lookup.json"))

        stats["output_files"] = [
            "ddxplus_pathology_documents.jsonl",
            "ddxplus_patient_descriptions.jsonl",
            "ddxplus_evidence_lookup.json",
        ]
        return stats

    def _build_pathology_docs(self) -> list[dict]:
        severity_map = {1: "critique", 2: "grave", 3: "moderee", 4: "legere", 5: "benigne"}
        docs = []
        for _, p in self.pathologies.items():
            sym_texts = []
            for s in p.symptoms:
                e = self.evi_registry.get(s)
                sym_texts.append(e.question_fr.rstrip("?").strip() if e else s.replace("_", " "))

            ant_texts = []
            for a in p.antecedents:
                e = self.evi_registry.get(a)
                ant_texts.append(e.question_fr.rstrip("?").strip() if e else a.replace("_", " "))

            sev = severity_map.get(p.severity, f"niveau {p.severity}")
            parts = [
                f"Pathologie : {p.name_fr} ({p.name_en}).",
                f"Code CIM-10 : {p.icd10_id}. Severite : {sev}.",
            ]
            if sym_texts:
                parts.append(f"Symptomes : {' ; '.join(sym_texts)}.")
            if ant_texts:
                parts.append(f"Facteurs de risque : {' ; '.join(ant_texts)}.")

            docs.append({
                "id": f"patho_{hashlib.md5(p.condition_name.encode()).hexdigest()[:12]}",
                "source": "ddxplus",
                "type": "pathology_document",
                "text": " ".join(parts),
                "pathology_fr": p.name_fr,
                "pathology_en": p.name_en,
                "icd10": p.icd10_id,
                "severity": p.severity,
            })
        return docs

    def _build_patient_docs(self) -> tuple[list[dict], list[str]]:
        docs = []
        patho_list = []

        with open(self.patients_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if self.max_patients and i >= self.max_patients:
                    break

                patient = self._parse_patient(row)
                if not patient:
                    continue

                doc = self._patient_to_doc(patient)
                if doc:
                    docs.append(doc)
                    patho_list.append(patient.pathology)

                if (i + 1) % 100000 == 0:
                    logger.info(f"    {i + 1} patients traites...")

        return docs, patho_list

    def _parse_patient(self, row: dict) -> Optional[Patient]:
        try:
            evidences_raw = row.get("EVIDENCES", "")
            if not evidences_raw:
                return None
            evidences = self._parse_list(evidences_raw)
            if not evidences:
                return None

            diff_raw = row.get("DIFFERENTIAL_DIAGNOSIS", "")
            diff = []
            if diff_raw and diff_raw != "[]":
                try:
                    parsed = json.loads(diff_raw.replace("'", '"'))
                    diff = [(p[0], float(p[1])) for p in parsed]
                except Exception:
                    pass

            return Patient(
                age=int(row.get("AGE", 0)),
                sex=row.get("SEX", ""),
                pathology=row.get("PATHOLOGY", ""),
                evidences=evidences,
                differential_diagnosis=diff,
                initial_evidence=row.get("INITIAL_EVIDENCE", ""),
            )
        except Exception:
            return None

    def _parse_list(self, raw: str) -> list[str]:
        raw = raw.strip()
        if raw.startswith("["):
            try:
                return json.loads(raw.replace("'", '"'))
            except json.JSONDecodeError:
                pass
        for sep in [";", "|", ","]:
            if sep in raw:
                return [e.strip().strip('"').strip("'") for e in raw.split(sep) if e.strip()]
        return [raw] if raw else []

    def _patient_to_doc(self, p: Patient) -> Optional[dict]:
        sym_texts, ant_texts = [], []
        for code in p.evidences:
            base = code.split("_@_")[0] if "_@_" in code else code
            evi = self.evi_registry.get(base)
            text = self.evi_registry.code_to_text(code)
            if evi and evi.is_antecedent:
                ant_texts.append(text)
            else:
                sym_texts.append(text)

        if not sym_texts:
            return None

        sex_t = "homme" if p.sex == "M" else "femme"
        parts = [f"Patient {sex_t} de {p.age} ans."]
        parts.append(f"Symptomes : {' ; '.join(sym_texts)}.")
        if ant_texts:
            parts.append(f"Antecedents : {' ; '.join(ant_texts)}.")

        diff_text = ""
        if p.differential_diagnosis:
            dd = []
            for pname, prob in p.differential_diagnosis[:5]:
                patho = self.pathologies.get(pname)
                dd.append(f"{patho.name_fr if patho else pname} ({prob * 100:.0f}%)")
            diff_text = " ; ".join(dd)

        pid = hashlib.md5(f"{p.age}_{p.sex}_{p.pathology}_{'_'.join(p.evidences[:3])}".encode()).hexdigest()[:12]

        patho_obj = self.pathologies.get(p.pathology)
        return {
            "id": f"patient_{pid}",
            "source": "ddxplus",
            "type": "patient_description",
            "text": " ".join(parts),
            "pathology_fr": patho_obj.name_fr if patho_obj else p.pathology,
            "age": p.age,
            "sex": p.sex,
            "differential_diagnosis": diff_text,
        }

    @staticmethod
    def _write_jsonl(docs: list[dict], path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for d in docs:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")


# ===================================================================
# 2. FINESS PROCESSOR
# ===================================================================


class FINESSProcessor:
    """
    Transforme les CSV FINESS bruts en documents normalises pour MongoDB.

    Responsabilites :
      - Filtrer les categories pertinentes (hopitaux, cliniques, centres de sante)
      - Joindre les donnees de geolocalisation
      - Convertir les coordonnees Lambert93 en WGS84 (lat/lon)
      - Normaliser les adresses
      - Produire un JSONL pret pour l'import MongoDB avec index 2dsphere
    """

    RELEVANT_CATEGORIES = {
        "101": "Centre Hospitalier Régional (C.H.R.)",
        "106": "Hôpital Militaire du Service de Santé des Armées",
        "109": "Centre Hospitalier Spécialisé Lutte Maladies Mentales",
        "114": "Hôpital Local",
        "122": "Établissement de Soins Pluridisciplinaire",
        "124": "Établissement de Soins Chirurgicaux",
        "128": "Hôpital des Armées",
        "129": "Établissement de Soins Médicaux",
        "131": "Établissement de Soins Obstétricaux",
        "141": "Centre de Lutte Contre le Cancer",
        "146": "Centre Hospitalier (C.H.)",
        "156": "Centre Médico-Psychologique (C.M.P.)",
        "161": "Établissement de Soins de Longue Durée",
        "182": "Service d'Éducation Spéciale et de Soins à Domicile",
        "197": "Structure d'Hospitalisation à Domicile",
        "213": "Centre de Médecine Préventive",
        "214": "Centre de Soins Médicaux",
        "219": "Autre Centre de Soins et de Prévention",
        "221": "Centre de Lutte contre la Tuberculose",
        "223": "Centre de Soins Infirmiers",
        "228": "Centre de Santé",
        "230": "Laboratoire d'Analyses et de Biologie Médicale",
        "233": "Pharmacie Mutualiste ou de Société de Secours Minière",
        "246": "Cabinet Médical",
        "250": "Consultation Dépistage Anonyme et Gratuit (C.D.A.G.)",
        "262": "Centre de Santé Mentale",
        "289": "Centre de Soins d'Accompagnement et de Prévention en Addictologie",
        "292": "Centre Antipoison",
        "344": "Maison de Santé",
        "354": "Maison de Santé Pluriprofessionnelle",
        "355": "Centre Hospitalier Universitaire (C.H.U.)",
        "362": "Établissement Thermal",
        "500": "Établissement d'Hébergement pour Personnes Âgées Dépendantes",
        "603": "Maison de Santé (L.6223-3)",
        "620": "Pharmacie d'Officine",
    }

    def __init__(self, etab_path: str, geo_path: Optional[str] = None):
        self.etab_path = etab_path
        # Les lignes 'geolocalisation' sont dans le fichier principal (etab_path)
        # geo_path est accepte pour compatibilite mais non utilise
        self.geo_path = geo_path

    def process(self, output_dir: Path) -> dict:
        logger.info("=" * 60)
        logger.info("[2/3] Traitement FINESS")
        logger.info("=" * 60)

        stats = {"source": "finess"}

        # Chargement simultane : etablissements ET geolocalisation depuis le meme fichier
        centers, geo_count = self._load_etablissements_and_geo()
        stats["total_raw"] = len(centers)
        stats["geolocalized"] = geo_count
        logger.info(f"  Etablissements charges : {len(centers)}")
        logger.info(f"  Geolocalisations trouvees : {geo_count}")

        filtered = {fid: c for fid, c in centers.items() if c.category_code in self.RELEVANT_CATEGORIES}
        stats["filtered_relevant"] = len(filtered)
        logger.info(f"  Apres filtrage categories pertinentes : {len(filtered)}")

        geolocated = {fid: c for fid, c in filtered.items() if c.latitude is not None and c.longitude is not None}
        stats["with_coordinates"] = len(geolocated)
        logger.info(f"  Avec coordonnees valides : {len(geolocated)}")

        docs = self._to_documents(geolocated)
        out_path = output_dir / "finess_health_centers.jsonl"
        self._write_jsonl(docs, out_path)
        stats["output_documents"] = len(docs)
        logger.info(f"  -> {len(docs)} centres exportes")

        cat_dist = Counter(c.category_label for c in geolocated.values())
        stats["category_distribution"] = dict(cat_dist.most_common(15))

        dep_dist = Counter(c.department_name for c in geolocated.values() if c.department_name)
        stats["departments_covered"] = len(dep_dist)

        stats["output_files"] = ["finess_health_centers.jsonl"]
        return stats

    def _load_etablissements_and_geo(self) -> tuple[dict[str, HealthCenter], int]:
        """
        Charge en une seule passe les etablissements ET les coordonnees.
        Format FINESS : le meme fichier contient des lignes 'structureet'
        et des lignes 'geolocalisation' intercalees.
        """
        centers: dict[str, HealthCenter] = {}
        geo_coords: dict[str, tuple[float, float]] = {}
        encoding = self._detect_encoding(self.etab_path)

        with open(self.etab_path, "r", encoding=encoding, errors="replace") as f:
            reader = csv.reader(f, delimiter=";")
            for row in reader:
                if not row:
                    continue

                row_type = row[0].strip()

                # Ligne d'etablissement
                if row_type == "structureet" and len(row) >= 22:
                    fid = row[1].strip()
                    if not fid:
                        continue
                    centers[fid] = HealthCenter(
                        finess_id=fid,
                        name=row[3].strip(),
                        name_long=row[4].strip(),
                        address=self._build_address(row),
                        postal_code=self._extract_postal(row[15]),
                        city=self._extract_city(row[15]),
                        department=row[13].strip(),
                        department_name=row[14].strip(),
                        phone=self._clean_phone(row[16]),
                        category_code=row[18].strip(),
                        category_label=row[19].strip(),
                        aggregate_category=row[20].strip(),
                        aggregate_label=row[21].strip(),
                        specialty_code=row[26].strip() if len(row) > 26 else "",
                        specialty_label=row[27].strip() if len(row) > 27 else "",
                    )

                # Ligne de geolocalisation : geolocalisation;finess_id;coordX;coordY;...
                elif row_type == "geolocalisation" and len(row) >= 4:
                    fid = row[1].strip()
                    try:
                        x, y = float(row[2].strip()), float(row[3].strip())
                        geo_coords[fid] = (x, y)
                    except (ValueError, TypeError):
                        continue

        # Joindre les coordonnees aux etablissements
        geo_count = 0
        for fid, (x, y) in geo_coords.items():
            if fid not in centers:
                continue
            try:
                # Lambert93 (EPSG:2154) -> WGS84
                lat, lon = self._lambert93_to_wgs84(x, y)
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    centers[fid].latitude = round(lat, 6)
                    centers[fid].longitude = round(lon, 6)
                    geo_count += 1
            except Exception:
                continue

        return centers, geo_count

    @staticmethod
    def _lambert93_to_wgs84(x: float, y: float) -> tuple[float, float]:
        """Conversion Lambert93 (EPSG:2154) -> WGS84 (EPSG:4326)."""
        n = 0.7256077650
        c = 11754255.426
        xs = 700000.0
        ys = 12655612.050
        e = 0.08181919112
        lon_origin = math.radians(3.0)

        r = math.sqrt((x - xs) ** 2 + (y - ys) ** 2)
        if r == 0:
            return 0.0, 0.0

        gamma = math.atan((x - xs) / (ys - y))
        lon = gamma / n + lon_origin
        lat_iso = -1 / n * math.log(abs(r / c))

        phi = 2 * math.atan(math.exp(lat_iso)) - math.pi / 2
        for _ in range(10):
            sin_phi = math.sin(phi)
            phi_new = 2 * math.atan(
                math.exp(lat_iso + e / 2 * math.log((1 + e * sin_phi) / (1 - e * sin_phi)))
            ) - math.pi / 2
            if abs(phi_new - phi) < 1e-12:
                break
            phi = phi_new

        return math.degrees(phi), math.degrees(lon)

    def _to_documents(self, centers: dict[str, HealthCenter]) -> list[dict]:
        """Convertit en documents JSONL avec format GeoJSON pour MongoDB."""
        docs = []
        for fid, c in centers.items():
            doc = {
                "id": f"finess_{fid}",
                "source": "finess",
                "type": "health_center",
                "finess_id": fid,
                "name": c.name_long if c.name_long else c.name,
                "name_short": c.name,
                "address": c.address,
                "postal_code": c.postal_code,
                "city": c.city,
                "department": c.department_name,
                "phone": c.phone,
                "category": c.category_label,
                "category_code": c.category_code,
                "specialty": c.specialty_label,
                "specialty_code": c.specialty_code,
                "location": {
                    "type": "Point",
                    "coordinates": [c.longitude, c.latitude],
                },
                "text": (
                    f"{c.name_long or c.name}, {c.category_label}. "
                    f"Adresse : {c.address}. "
                    f"Departement : {c.department_name}. "
                    f"Telephone : {c.phone}."
                    + (f" Specialite : {c.specialty_label}." if c.specialty_label else "")
                ),
            }
            docs.append(doc)
        return docs

    def _build_address(self, row: list) -> str:
        parts = []
        numvoie = row[7].strip()
        typvoie = row[8].strip()
        voie = row[9].strip()
        if numvoie:
            parts.append(numvoie)
        if typvoie:
            parts.append(typvoie)
        if voie:
            parts.append(voie)
        address = " ".join(parts)
        ligne = row[15].strip() if len(row) > 15 else ""
        if ligne:
            address += f", {ligne}"
        return address

    @staticmethod
    def _extract_postal(ligne: str) -> str:
        m = re.match(r"(\d{5})", ligne.strip())
        return m.group(1) if m else ""

    @staticmethod
    def _extract_city(ligne: str) -> str:
        m = re.match(r"\d{5}\s+(.*)", ligne.strip())
        return m.group(1).strip() if m else ligne.strip()

    @staticmethod
    def _clean_phone(raw: str) -> str:
        digits = re.sub(r"\D", "", raw.strip())
        if len(digits) == 10:
            return f"{digits[0:2]} {digits[2:4]} {digits[4:6]} {digits[6:8]} {digits[8:10]}"
        return digits

    @staticmethod
    def _detect_encoding(path: str) -> str:
        for enc in ["utf-8", "latin-1", "iso-8859-1", "cp1252"]:
            try:
                with open(path, "r", encoding=enc) as f:
                    f.read(10000)
                return enc
            except (UnicodeDecodeError, UnicodeError):
                continue
        return "latin-1"

    @staticmethod
    def _write_jsonl(docs: list[dict], path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for d in docs:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")


# ===================================================================
# 3. CSV SYMPTOMS PROCESSOR
# ===================================================================


class CSVSymptomsProcessor:
    """
    Nettoie et normalise le CSV combined_medical_data.csv.

    Responsabilites :
      - Supprimer les doublons
      - Equilibrer la distribution par pathologie (sous-echantillonnage)
      - Normaliser le format en JSONL coherent avec DDXPlus
    """

    def __init__(self, csv_path: str, max_per_pathology: int = 100):
        self.csv_path = csv_path
        self.max_per_pathology = max_per_pathology

    def process(self, output_dir: Path) -> dict:
        logger.info("=" * 60)
        logger.info("[3/3] Traitement CSV symptomes")
        logger.info("=" * 60)

        stats = {"source": "csv_symptoms"}

        rows = self._load_and_dedup()
        stats["total_raw"] = len(rows)
        logger.info(f"  Lignes apres deduplication : {len(rows)}")

        balanced = self._balance_classes(rows)
        stats["after_balancing"] = len(balanced)
        logger.info(f"  Lignes apres equilibrage (max {self.max_per_pathology}/classe) : {len(balanced)}")

        docs = self._to_documents(balanced)
        out_path = output_dir / "csv_symptom_descriptions.jsonl"
        self._write_jsonl(docs, out_path)
        stats["output_documents"] = len(docs)

        label_dist = Counter(r["label"] for r in balanced)
        stats["pathologies_count"] = len(label_dist)
        stats["pathology_distribution"] = dict(label_dist.most_common())
        stats["language"] = "en"
        stats["warning"] = "Donnees en anglais, 27 pathologies seulement. A utiliser pour evaluation."

        stats["output_files"] = ["csv_symptom_descriptions.jsonl"]
        logger.info(f"  -> {len(docs)} documents exportes ({len(label_dist)} pathologies)")
        return stats

    def _load_and_dedup(self) -> list[dict]:
        seen = set()
        rows = []
        with open(self.csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                text = row.get("text", "").strip()
                label = row.get("label", "").strip()
                if not text or not label:
                    continue
                key = hashlib.md5(f"{label}|{text}".encode()).hexdigest()
                if key in seen:
                    continue
                seen.add(key)
                rows.append({"label": label, "text": text})
        return rows

    def _balance_classes(self, rows: list[dict]) -> list[dict]:
        by_label = defaultdict(list)
        for r in rows:
            by_label[r["label"]].append(r)

        balanced = []
        for label, items in by_label.items():
            if len(items) > self.max_per_pathology:
                import random
                random.seed(42)
                items = random.sample(items, self.max_per_pathology)
            balanced.extend(items)
        return balanced

    def _to_documents(self, rows: list[dict]) -> list[dict]:
        docs = []
        for r in rows:
            rid = hashlib.md5(f"{r['label']}|{r['text']}".encode()).hexdigest()[:12]
            docs.append({
                "id": f"csv_{rid}",
                "source": "csv_symptoms",
                "type": "symptom_description",
                "text": r["text"],
                "pathology_en": r["label"],
                "language": "en",
            })
        return docs

    @staticmethod
    def _write_jsonl(docs: list[dict], path: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for d in docs:
                f.write(json.dumps(d, ensure_ascii=False) + "\n")


# ===================================================================
# PIPELINE UNIFIE
# ===================================================================


class UnifiedDataProcessor:
    """
    Orchestrateur principal. Execute les 3 processeurs et produit
    un rapport global de qualite.
    """

    def __init__(self, args):
        self.args = args
        self.output_dir = Path(args.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run(self) -> dict:
        start = datetime.now(timezone.utc)
        logger.info("#" * 60)
        logger.info("  PIPELINE UNIFIE DE DATA PROCESSING")
        logger.info(f"  Sortie : {self.output_dir}")
        logger.info("#" * 60)

        all_stats = {}

        if self.args.ddxplus_conditions and self.args.ddxplus_evidences and self.args.ddxplus_patients:
            proc = DDXPlusProcessor(
                self.args.ddxplus_conditions,
                self.args.ddxplus_evidences,
                self.args.ddxplus_patients,
                max_patients=self.args.max_patients,
            )
            all_stats["ddxplus"] = proc.process(self.output_dir)
        else:
            logger.info("DDXPlus : fichiers non fournis, skip.")

        if self.args.finess_etab:
            proc = FINESSProcessor(
                self.args.finess_etab,
                self.args.finess_geo,
            )
            all_stats["finess"] = proc.process(self.output_dir)
        else:
            logger.info("FINESS : fichier non fourni, skip.")

        if self.args.csv_symptoms:
            proc = CSVSymptomsProcessor(
                self.args.csv_symptoms,
                max_per_pathology=self.args.max_per_pathology,
            )
            all_stats["csv_symptoms"] = proc.process(self.output_dir)
        else:
            logger.info("CSV symptoms : fichier non fourni, skip.")

        end = datetime.now(timezone.utc)
        report = {
            "pipeline": "unified_data_processor",
            "version": "1.0.0",
            "started_at": start.isoformat(),
            "completed_at": end.isoformat(),
            "duration_seconds": round((end - start).total_seconds(), 1),
            "sources_processed": list(all_stats.keys()),
            "stats": all_stats,
            "output_directory": str(self.output_dir),
            "all_output_files": sorted(
                [f for s in all_stats.values() for f in s.get("output_files", [])]
            ),
            "next_steps": [
                "Phase 4 : Vectoriser *_documents.jsonl et *_descriptions.jsonl avec EmbeddingManager",
                "Phase 4 : Stocker embeddings dans pgvector",
                "Phase 4 : Importer finess_health_centers.jsonl dans MongoDB avec index 2dsphere",
                "Phase 5 : Configurer le RAGEngine (Langchain + retriever pgvector)",
            ],
        }

        report_path = self.output_dir / "processing_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        logger.info("")
        logger.info("#" * 60)
        logger.info(f"  PIPELINE TERMINE en {report['duration_seconds']}s")
        logger.info(f"  Sources : {', '.join(report['sources_processed'])}")
        logger.info(f"  Fichiers generes : {len(report['all_output_files'])}")
        logger.info(f"  Rapport : {report_path}")
        logger.info("#" * 60)

        logger.info("")
        logger.info(f"  {self.output_dir}/")
        for f in sorted(self.output_dir.iterdir()):
            size = f.stat().st_size / (1024 * 1024)
            logger.info(f"    {f.name:50s} {size:8.2f} Mo")

        return report


# ===================================================================
# CLI
# ===================================================================


def parse_args():
    p = argparse.ArgumentParser(
        description="Pipeline unifie de data processing pour le projet RAG medical",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  # Tout traiter
  python unified_data_processor.py \\
    --ddxplus-conditions release_conditions.json \\
    --ddxplus-evidences release_evidences.json \\
    --ddxplus-patients release_train_patients.csv \\
    --finess-etab finess_etablissements.csv \\
    --finess-geo finess_geolocalisation.csv \\
    --csv-symptoms combined_medical_data.csv \\
    --output-dir ./processed --max-patients 100000

  # Seulement FINESS
  python unified_data_processor.py \\
    --finess-etab finess_etablissements.csv \\
    --finess-geo finess_geolocalisation.csv \\
    --output-dir ./processed
        """,
    )
    p.add_argument("--ddxplus-conditions", default=None)
    p.add_argument("--ddxplus-evidences", default=None)
    p.add_argument("--ddxplus-patients", default=None)
    p.add_argument("--max-patients", type=int, default=None, help="Limite de patients DDXPlus")
    p.add_argument("--finess-etab", default=None)
    p.add_argument("--finess-geo", default=None)
    p.add_argument("--csv-symptoms", default=None)
    p.add_argument("--max-per-pathology", type=int, default=100, help="Max echantillons par pathologie CSV")
    p.add_argument("--output-dir", default="./processed")
    return p.parse_args()


def main():
    args = parse_args()
    pipeline = UnifiedDataProcessor(args)
    pipeline.run()


if __name__ == "__main__":
    main()
