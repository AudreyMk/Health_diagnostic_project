"""Test rapide : verifie que /centers gere bien dept ET lat/lon."""
import requests

BASE = "http://127.0.0.1:8000"

# Login d abord (on assume que test@test.com existe)
print("=== Login ===")
r = requests.post(f"{BASE}/auth/login", json={"email": "test@test.com", "password": "test123"})
print(f"  status={r.status_code}")
if r.status_code != 200:
    print(f"  {r.text}")
    raise SystemExit(1)
token = r.json()["session_token"]
headers = {"Authorization": f"Bearer {token}"}

print("\n=== Test 1: /centers?dept=35 (Rennes) ===")
r = requests.get(f"{BASE}/centers", params={"dept": "35"}, headers=headers)
print(f"  status={r.status_code}, source={r.json().get('source')}, n={len(r.json().get('centers', []))}")
for c in r.json().get("centers", [])[:3]:
    print(f"    - {c['name'][:50]} | {c.get('address', '')[:30]}")

print("\n=== Test 2: /centers?lat=48.8566&lon=2.3522&radius=2000 (Paris centre, 2 km) ===")
r = requests.get(f"{BASE}/centers", params={"lat": 48.8566, "lon": 2.3522, "radius": 2000}, headers=headers)
print(f"  status={r.status_code}, source={r.json().get('source')}, n={len(r.json().get('centers', []))}")
for c in r.json().get("centers", [])[:3]:
    loc = c.get("location", {}).get("coordinates", [None, None])
    print(f"    - {c['name'][:50]} | lon={loc[0]:.4f} lat={loc[1]:.4f}" if loc[0] else f"    - {c['name'][:50]} | (pas de coords)")

print("\n=== Test 3: /centers (sans rien -> fallback sur dept du user) ===")
r = requests.get(f"{BASE}/centers", headers=headers)
print(f"  status={r.status_code}, source={r.json().get('source')}, n={len(r.json().get('centers', []))}")
