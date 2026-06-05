"""
debug_finess.py — Inspecte le fichier FINESS ligne par ligne (acces positionnel)
"""
import csv, io
import requests

URL = "https://www.data.gouv.fr/fr/datasets/r/2ce43ade-8d2c-4d1d-81da-ca06c82abc68"

print("Telechargement (300 ko)...")
resp = requests.get(URL, stream=True, timeout=120)
resp.raise_for_status()

chunk = b""
for part in resp.iter_content(chunk_size=32768):
    chunk += part
    if len(chunk) > 400_000:
        break
resp.close()

raw = chunk.decode("latin-1")

reader = csv.reader(io.StringIO(raw), delimiter=";")

# Ligne 1 : metadonnees
meta = next(reader)
print(f"\nLigne 1 (metadonnees) : {meta}")

# Lignes 2 a 6 : donnees reelles
print("\nColonnes des 5 premieres lignes de donnees :")
for i, row in enumerate(reader):
    if i >= 5:
        break
    print(f"\n--- Ligne {i+2} ({len(row)} colonnes) ---")
    for j, val in enumerate(row):
        print(f"  [{j:2d}] {val!r}")
