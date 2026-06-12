"""
test_questioning.py — Teste la qualité du questionnement (anti faux red flag).

Régression de l'incident "mal de gorge -> SAMU sur tout oui" : un patient
pressé qui répond "oui" à tout, MAIS qui n'a pas réellement de signe d'alarme,
ne doit PAS être sur-trié en urgence/SAMU. L'agent doit isoler chaque red flag
et obtenir une réponse claire avant de fonder une orientation dessus.

NB : le harness principal (run_eval.py) tolère le sur-triage par conception ;
ce test est précisément là pour attraper le sur-triage injustifié sur ce cas.

Usage :
  .venv/Scripts/python.exe evaluation/test_questioning.py
"""
import sys
import requests

BASE     = "http://localhost:8010/api"
PASSWORD = "eval_medrag_2026"
MAX_TOURS = 8

# Le faux patient répond "Oui" par défaut (acquiesce vaguement), SAUF sur les
# signes d'alarme réels, où il répond clairement par la négative.
REPONSES = [
    {"si": ["respir", "souffl", "essouffl"], "rep": "Non, je respire tout a fait normalement."},
    {"si": ["avaler", "salive", "deglu", "dégluti", "baver"], "rep": "Non, j'avale sans aucun probleme."},
    {"si": ["etouff", "étouff"], "rep": "Non, rien de tout ca."},
    {"si": ["temperature", "température", "combien", "degre", "degré"], "rep": "38, je l'ai prise."},
    {"si": ["raideur", "nuque"], "rep": "Non, ma nuque est souple."},
    {"si": ["tache", "violac", "bouton"], "rep": "Non, pas de taches."},
]
DEFAUT = "Oui."   # le patient acquiesce vaguement a tout le reste


def session(email, age, sex):
    requests.post(f"{BASE}/auth/register", json={
        "name": "Test quest", "email": email, "password": PASSWORD, "age": age, "sex": sex})
    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": PASSWORD})
    r.raise_for_status()
    h = {"Authorization": f"Bearer {r.json()['token']}"}
    requests.put(f"{BASE}/auth/profile", json={"dept": "35"}, headers=h)
    requests.post(f"{BASE}/patient/profile", json={}, headers=h)
    return h


def repondre(question):
    q = question.lower()
    for item in REPONSES:
        if any(mot in q for mot in item["si"]):
            return item["rep"]
    return DEFAUT


def scenario_gorge():
    """Mal de gorge + fièvre, mais PAS de difficulté à respirer/avaler.
    Attendu : orientation médecin ou pharmacien — surtout PAS urgent/samu."""
    print("\n-- Mal de gorge febrile, patient qui dit 'oui' a tout --")
    h = session("test_quest_gorge@medrag.test", 25, "F")
    conv = requests.post(f"{BASE}/conversations", headers=h).json()["conversation_id"]

    message = "J'ai mal a la gorge depuis samedi et j'ai de la fievre. Je fais quoi ?"
    orientation = None
    for _ in range(MAX_TOURS):
        r = requests.post(f"{BASE}/conversations/{conv}/chat",
                          json={"content": message}, headers=h, timeout=180)
        r.raise_for_status()
        data = r.json()
        if data.get("triage"):
            orientation = data["triage"].get("orientation")
            break
        message = repondre(data.get("response", ""))

    print(f"   Orientation obtenue : {orientation}")
    # Le coeur du test : pas de sur-triage en urgence sans red flag reel
    ok = orientation in ("domicile", "pharmacien", "medecin")
    if ok:
        print("   OK  Pas de sur-triage injustifie (red flag absent correctement filtre)")
    else:
        print(f"   ECHEC : orientation '{orientation}' alors qu'aucun red flag n'est present.")
        print("   -> l'agent a probablement accepte un 'oui' vague sur un signe d'alarme.")
    return ok


def main():
    try:
        requests.get(f"{BASE}/health", timeout=10).raise_for_status()
    except Exception:
        print("ERREUR : l'API ne repond pas sur le port 8010.")
        sys.exit(2)

    ok = scenario_gorge()
    print("\n" + "=" * 50)
    if ok:
        print("QUESTIONNEMENT : le scenario passe.")
        sys.exit(0)
    print("QUESTIONNEMENT : ECHEC — corriger avant de deployer.")
    sys.exit(1)


if __name__ == "__main__":
    main()
