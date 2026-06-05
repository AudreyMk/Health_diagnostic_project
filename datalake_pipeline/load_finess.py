"""
load_finess.py — Charge les etablissements FINESS dans MongoDB (filtre par departement).
Format : CSV UTF-8, separateur ';', premiere ligne = metadonnees (pas un header).
Colonnes positionnelles (32 colonnes par ligne de type 'structureet') :
  [0]  type de ligne ('structureet')
  [2]  nofinesset
  [4]  nom long
  [13] code departement (ex: '35')
  [15] adresse (ligneacheminement)
  [16] telephone
  [18] code categorie
  [19] libelle categorie

Usage :
  python load_finess.py
"""
import csv, io, sys
from collections import Counter
from pathlib import Path
from dotenv import load_dotenv
import os
import requests
from pymongo import MongoClient

# Charge le .env du dossier datalake_pipeline
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ── Config ────────────────────────────────────────────────────────────────────

MONGO_URI = os.getenv("MONGO_URI", "mongodb://medrag:medrag_2024@localhost:27018/")
DB_NAME   = "medrag"
COLL_NAME = "health_centers"
URL       = "https://www.data.gouv.fr/fr/datasets/r/2ce43ade-8d2c-4d1d-81da-ca06c82abc68"

# Mots-cles dans libcategorie [19] pour garder les etablissements utiles
# (en minuscules, sans accents pour eviter les problemes d'encodage)
KEYWORDS = [
    "hospitalier", "hopital", "clinique",
    "sant",          # sante, sante, maison de sante...
    "cabinet",       # cabinet medical, cabinet de groupe
    "pharmacie",
    "samu", "smur", "urgence",
    "medical",       # centre medical
    "soins",         # centre de soins
]

# Indices de colonnes
C_TYPE     = 0
C_FINESS   = 2
C_NOM      = 4
C_DEPT     = 13
C_ADRESSE  = 15
C_TEL      = 16
C_CATCODE  = 18
C_CATLABEL = 19


def col(row, idx):
    """Lecture securisee d une colonne par index."""
    try:
        return row[idx].strip()
    except IndexError:
        return ""


def is_useful(libcat):
    low = libcat.lower()
    return any(kw in low for kw in KEYWORDS)


def main():
    print("Telechargement FINESS...")
    resp = requests.get(URL, stream=True, timeout=300)
    resp.raise_for_status()

    # Le fichier est UTF-8 malgre l extension .csv (confirm par les accents)
    raw = resp.content.decode("utf-8", errors="replace")

    reader = csv.reader(io.StringIO(raw), delimiter=";")
    next(reader)  # ignorer la ligne de metadonnees

    centers = []
    seen_cats = Counter()

    for row in reader:
        if col(row, C_TYPE) != "structureet":
            continue

        libcat = col(row, C_CATLABEL)
        seen_cats[libcat] += 1

        if not is_useful(libcat):
            continue

        dept = col(row, C_DEPT)
        # Garde uniquement la metropole (2 chiffres, 01..95 + 2A/2B)
        if not dept or (not dept.isdigit() and dept not in ("2A", "2B")):
            continue

        centers.append({
            "finess":         col(row, C_FINESS),
            "name":           col(row, C_NOM),
            "category_code":  col(row, C_CATCODE),
            "category_label": libcat,
            "address":        col(row, C_ADRESSE),
            "phone":          col(row, C_TEL),
            "dept":           dept,
        })

    print(f"\nEtablissements filtres : {len(centers)}")

    if not centers:
        print("\nTop categories vues (non filtrees) :")
        for lab, n in seen_cats.most_common(20):
            print(f"  {n:5d}  {lab!r}")
        print("\nERREUR : aucun etablissement utile. Verifiez les keywords.")
        sys.exit(1)

    print("Chargement dans MongoDB...")
    client = MongoClient(MONGO_URI)
    coll   = client[DB_NAME][COLL_NAME]
    coll.drop()
    coll.create_index("dept")
    coll.create_index("category_code")
    coll.insert_many(centers, ordered=False)

    total = coll.count_documents({})
    print(f"Total charge : {total} etablissements\n")

    print("Top 15 categories :")
    cat_counts = Counter(c["category_label"] for c in centers)
    for lab, n in cat_counts.most_common(15):
        print(f"  {n:5d}  {lab}")

    client.close()
    print("\nTermine !")


if __name__ == "__main__":
    main()
