"""
load_finess.py — Charge les etablissements FINESS geolocalises dans MongoDB.

Source : "Extraction Finess des Etablissements geolocalises" (data.gouv.fr).
Le CSV contient 2 types de lignes (separateur ';', UTF-8) :
  - 'structureet'     : 32 colonnes, infos etablissement
  - 'geolocalisation' : 6 colonnes, coords Lambert93 (EPSG:2154)
Jointure par col[1] (nofinessej) — meme cle dans les deux types.
Conversion Lambert93 -> WGS84 (EPSG:4326) via pyproj.
Stockage en GeoJSON Point + index 2dsphere pour requetes $near.

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
from pyproj import Transformer

load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# ── Config ────────────────────────────────────────────────────────────────────

MONGO_URI = os.getenv("MONGO_URI", "mongodb://medrag:medrag_2024@localhost:27018/")
DB_NAME   = "medrag"
COLL_NAME = "health_centers"
# Fichier FINESS *geolocalise* (~45 Mo, contient struct + geoloc)
URL       = "https://www.data.gouv.fr/api/1/datasets/r/98f3161f-79ff-4f16-8f6a-6d571a80fea2"

# Mots-cles dans libcategorie pour garder les etablissements utiles
KEYWORDS = [
    "hospitalier", "hopital", "clinique",
    "sant",          # sante, maison de sante...
    "cabinet",
    "pharmacie",
    "samu", "smur", "urgence",
    "medical",
    "soins",
]

# Indices structureet (32 colonnes)
C_KEY      = 1   # nofinessej : cle de jointure
C_FINESS   = 2   # nofinesset : identifiant unique etablissement
C_NOM      = 4
C_DEPT     = 13
C_ADRESSE  = 15
C_TEL      = 16
C_CATCODE  = 18
C_CATLABEL = 19

# Indices geolocalisation (6 colonnes)
G_KEY = 1
G_X   = 2        # X Lambert93
G_Y   = 3        # Y Lambert93

# Transformer Lambert93 (RGF93 metropole) -> WGS84
# always_xy=True garantit l ordre (lon, lat) en sortie (standard GeoJSON)
_TRANSFORMER = Transformer.from_crs("EPSG:2154", "EPSG:4326", always_xy=True)


def col(row, idx):
    try:
        return row[idx].strip()
    except IndexError:
        return ""


def is_useful(libcat):
    low = libcat.lower()
    return any(kw in low for kw in KEYWORDS)


def lambert93_to_wgs84(x_str, y_str):
    """Retourne (longitude, latitude) ou None si invalide."""
    try:
        x = float(x_str.replace(",", "."))
        y = float(y_str.replace(",", "."))
    except (ValueError, AttributeError):
        return None
    if x <= 0 or y <= 0:
        return None
    lon, lat = _TRANSFORMER.transform(x, y)
    # Garde-fou France metropolitaine (rejette outliers)
    if not (-5.5 <= lon <= 10.0 and 41.0 <= lat <= 51.5):
        return None
    return lon, lat


def main():
    print("Telechargement FINESS geolocalise (~45 Mo)...")
    resp = requests.get(URL, stream=True, timeout=600)
    resp.raise_for_status()
    raw = resp.content.decode("utf-8", errors="replace")
    print(f"Recu : {len(raw):,} caracteres")

    reader = csv.reader(io.StringIO(raw), delimiter=";")
    next(reader)  # ligne de metadonnees

    structures = []    # etablissements apres filtrage
    geolocs = {}       # nofinessej -> (lon, lat)
    seen_cats = Counter()
    geoloc_invalid = 0

    for row in reader:
        if not row:
            continue
        t = col(row, 0)

        if t == "structureet":
            libcat = col(row, C_CATLABEL)
            seen_cats[libcat] += 1
            if not is_useful(libcat):
                continue
            dept = col(row, C_DEPT)
            # metropole uniquement
            if not dept or (not dept.isdigit() and dept not in ("2A", "2B")):
                continue
            structures.append({
                "_key":           col(row, C_KEY),
                "finess":         col(row, C_FINESS),
                "name":           col(row, C_NOM),
                "category_code":  col(row, C_CATCODE),
                "category_label": libcat,
                "address":        col(row, C_ADRESSE),
                "phone":          col(row, C_TEL),
                "dept":           dept,
            })

        elif t == "geolocalisation":
            key = col(row, G_KEY)
            coords = lambert93_to_wgs84(col(row, G_X), col(row, G_Y))
            if key and coords:
                geolocs[key] = coords
            else:
                geoloc_invalid += 1

    print(f"\nStructures filtrees     : {len(structures):,}")
    print(f"Geoloc valides (total)  : {len(geolocs):,}")
    print(f"Geoloc rejetees         : {geoloc_invalid:,}")

    if not structures:
        print("\nTop categories vues (non filtrees) :")
        for lab, n in seen_cats.most_common(20):
            print(f"  {n:5d}  {lab!r}")
        print("\nERREUR : aucun etablissement utile.")
        sys.exit(1)

    # Enrichir chaque etablissement avec sa geolocalisation
    enriched = []
    with_geo = 0
    for s in structures:
        coords = geolocs.get(s.pop("_key", ""))
        if coords:
            lon, lat = coords
            s["location"] = {"type": "Point", "coordinates": [lon, lat]}
            with_geo += 1
        enriched.append(s)

    pct = 100 * with_geo / len(enriched) if enriched else 0
    print(f"Etablissements geolocs  : {with_geo:,} / {len(enriched):,} ({pct:.1f}%)")

    print("\nChargement dans MongoDB...")
    client = MongoClient(MONGO_URI)
    coll   = client[DB_NAME][COLL_NAME]
    coll.drop()
    coll.insert_many(enriched, ordered=False)

    # Index : dept, category_code, et 2dsphere sur location pour $near
    coll.create_index("dept")
    coll.create_index("category_code")
    coll.create_index([("location", "2dsphere")])

    total    = coll.count_documents({})
    with_loc = coll.count_documents({"location": {"$exists": True}})
    print(f"\nTotal en base : {total:,} etablissements")
    print(f"Avec geoloc   : {with_loc:,} (interrogeables via $near)")

    print("\nTop 15 categories :")
    cat_counts = Counter(c["category_label"] for c in enriched)
    for lab, n in cat_counts.most_common(15):
        print(f"  {n:5d}  {lab}")

    client.close()
    print("\nTermine !")


if __name__ == "__main__":
    main()
