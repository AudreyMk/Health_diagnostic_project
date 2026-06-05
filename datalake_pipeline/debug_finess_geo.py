"""
debug_finess_geo.py — Inspecte la structure des lignes 'geolocalisationet' du fichier FINESS.
Telecharge ~1 Mo, decompte les types de lignes et affiche 3 echantillons de chaque type.
"""
import csv, io
from collections import Counter
import requests

URL = "https://www.data.gouv.fr/api/1/datasets/r/98f3161f-79ff-4f16-8f6a-6d571a80fea2"

print("Telechargement (~3 Mo)...")
resp = requests.get(URL, stream=True, timeout=120)
resp.raise_for_status()
raw = resp.content.decode("utf-8", errors="replace")
print(f"Taille recue : {len(raw)} caracteres")

reader = csv.reader(io.StringIO(raw), delimiter=";")
next(reader)  # metadonnees

types_count = Counter()
samples = {}

for row in reader:
    if not row:
        continue
    t = row[0].strip()
    types_count[t] += 1
    if t not in samples:
        samples[t] = []
    if len(samples[t]) < 3:
        samples[t].append(row)

print("\n=== Types de lignes ===")
for t, n in types_count.most_common():
    print(f"  {n:7d}  {t!r}")

for t, rows in samples.items():
    print(f"\n=== Echantillons type {t!r} ({len(rows[0])} colonnes) ===")
    for i, row in enumerate(rows):
        print(f"\n--- Echantillon {i+1} ({len(row)} colonnes) ---")
        for j, val in enumerate(row):
            print(f"  [{j:2d}] {val!r}")
