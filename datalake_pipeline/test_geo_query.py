"""Test rapide des requetes geospatiales $near sur la collection FINESS enrichie."""
import os
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv(Path(__file__).parent / ".env")
client = MongoClient(os.getenv("MONGO_URI", "mongodb://medrag:medrag_2024@localhost:27018/"))
coll = client["medrag"]["health_centers"]

print("=== Stats ===")
print(f"Total documents : {coll.count_documents({})}")
print(f"Avec location   : {coll.count_documents({'location': {'$exists': True}})}")
print()

print("=== Test 1: 5 etablissements autour de Notre-Dame Paris (rayon 2 km) ===")
q = {"location": {"$near": {"$geometry": {"type": "Point", "coordinates": [2.3499, 48.8530]}, "$maxDistance": 2000}}}
for d in coll.find(q).limit(5):
    print(f"  - {d['name'][:55]:55s} | {d['category_label'][:30]:30s} | dept {d['dept']}")

print()
print("=== Test 2: 3 hopitaux (cat 355) autour de Marseille (lon=5.37, lat=43.30, rayon 30 km) ===")
q = {
    "location": {"$near": {"$geometry": {"type": "Point", "coordinates": [5.37, 43.30]}, "$maxDistance": 30000}},
    "category_code": "355",
}
for d in coll.find(q).limit(3):
    print(f"  - {d['name'][:55]:55s} | {d['address'][:30]}")

print()
print("=== Test 3: 3 pharmacies (cat 620) autour de Rennes (lon=-1.68, lat=48.11, rayon 1 km) ===")
q = {
    "location": {"$near": {"$geometry": {"type": "Point", "coordinates": [-1.68, 48.11]}, "$maxDistance": 1000}},
    "category_label": {"$regex": "^Pharmacie", "$options": "i"},
}
for d in coll.find(q).limit(3):
    print(f"  - {d['name'][:55]:55s} | {d['address'][:30]}")

print()
print("=== Index actifs ===")
for idx in coll.list_indexes():
    print(f"  {idx['name']}: {dict(idx.get('key', {}))}")

client.close()
