"""
run_eval.py — Harness d'évaluation du triage MedRAG.

Joue les vignettes cliniques (vignettes.json) contre l'API locale et mesure :
  - le taux de réponses exactes
  - le taux de SOUS-triage  (cas grave classé bénin = échec critique)
  - le taux de sur-triage   (prudence excessive = acceptable)

Prérequis : Docker (postgres + mongo) démarré, API FastAPI sur le port 8010.

Usage :
  python evaluation/run_eval.py             -> toutes les vignettes
  python evaluation/run_eval.py --only v01  -> une seule vignette
"""
import argparse
import json
import os
import sys
from pathlib import Path

import requests

BASE      = os.getenv("MEDRAG_API_BASE", "http://localhost:8010/api")
PASSWORD  = "eval_medrag_2026"   # mot de passe commun aux comptes de test
MAX_TOURS = 6                    # tours de conversation max par vignette

# Échelle de gravité des orientations (pour détecter le sous-triage)
SEVERITE = {"domicile": 0, "pharmacien": 1, "medecin": 2, "urgent": 3, "samu": 4}


def creer_session(vignette):
    """Crée (ou réutilise) le compte de test dédié à la vignette,
    renseigne son profil médical, et retourne les headers d'auth."""
    email  = f"eval_{vignette['id']}@medrag.test"
    profil = vignette.get("profil", {})

    # L'inscription échoue avec 400 si le compte existe déjà : pas grave
    requests.post(f"{BASE}/auth/register", json={
        "name": f"Eval {vignette['id']}",
        "email": email,
        "password": PASSWORD,
        "age": profil.get("age"),
        "sex": profil.get("sex"),
    })

    r = requests.post(f"{BASE}/auth/login", json={"email": email, "password": PASSWORD})
    r.raise_for_status()
    headers = {"Authorization": f"Bearer {r.json()['token']}"}

    # Département + profil médical (teste aussi l'injection du profil dans le prompt)
    requests.put(f"{BASE}/auth/profile", json={"dept": profil.get("dept", "75")}, headers=headers)
    requests.post(f"{BASE}/patient/profile", json={
        "antecedents": profil.get("antecedents", []),
        "treatments":  profil.get("treatments", []),
        "allergies":   profil.get("allergies", []),
    }, headers=headers)

    return headers


def reponse_patient(question_agent, vignette):
    """Choisit la réponse du faux patient à la question posée par l'agent."""
    q = question_agent.lower()
    for item in vignette.get("reponses", []):
        if any(mot.lower() in q for mot in item["si_question_contient"]):
            return item["reponse"]
    return vignette.get("reponse_par_defaut", "Non, rien d'autre à signaler.")


def jouer_vignette(vignette):
    """Joue la vignette en entier. Retourne (orientation_finale, nb_tours)."""
    headers = creer_session(vignette)
    conv_id = requests.post(f"{BASE}/conversations", headers=headers).json()["conversation_id"]

    message = vignette["description"]
    for tour in range(1, MAX_TOURS + 1):
        r = requests.post(
            f"{BASE}/conversations/{conv_id}/chat",
            json={"content": message}, headers=headers, timeout=180,
        )
        r.raise_for_status()
        data = r.json()

        if data.get("triage"):
            return data["triage"].get("orientation"), tour

        # Pas encore de triage : l'agent pose une question, le faux patient répond
        message = reponse_patient(data.get("response", ""), vignette)

    return None, MAX_TOURS


def evaluer(orientation, vignette):
    """Compare l'orientation obtenue à l'attendu.
    Retourne : 'exact' | 'sur-triage' | 'SOUS-TRIAGE' | 'aucun triage'."""
    if orientation is None:
        return "aucun triage"
    attendu = vignette["orientation_attendue"]
    if orientation == attendu or orientation in vignette.get("acceptables", []):
        return "exact"
    if SEVERITE.get(orientation, -1) < SEVERITE[attendu]:
        return "SOUS-TRIAGE"
    return "sur-triage"


def main():
    parser = argparse.ArgumentParser(description="Harness d'évaluation du triage MedRAG")
    parser.add_argument("--only", help="ne jouer qu'une vignette (ex: v01)")
    args = parser.parse_args()

    # Vérifie que l'API est démarrée avant de commencer
    try:
        requests.get(f"{BASE}/health", timeout=10).raise_for_status()
    except Exception:
        print(f"ERREUR : l'API ne répond pas sur {BASE}.")
        print("Démarrez-la d'abord, ou pointez vers une instance existante :")
        print("  $env:MEDRAG_API_BASE = 'http://localhost:8000/api'")
        sys.exit(2)

    fichier = Path(__file__).parent / "vignettes.json"
    vignettes = json.loads(fichier.read_text(encoding="utf-8"))["vignettes"]
    if args.only:
        vignettes = [v for v in vignettes if v["id"] == args.only]
        if not vignettes:
            print(f"Vignette {args.only} introuvable.")
            sys.exit(2)

    resultats = []
    print(f"\n{'ID':<5} {'Vignette':<45} {'Attendu':<11} {'Obtenu':<11} {'Tours':<6} Verdict")
    print("-" * 100)

    for v in vignettes:
        try:
            orientation, tours = jouer_vignette(v)
        except Exception as e:
            orientation, tours = None, 0
            print(f"  !! erreur technique sur {v['id']}: {e}")

        verdict = evaluer(orientation, v)
        resultats.append(verdict)
        print(f"{v['id']:<5} {v['titre']:<45} {v['orientation_attendue']:<11} "
              f"{str(orientation):<11} {tours:<6} {verdict}")

    # ── Bilan ──────────────────────────────────────────────────────────────
    total       = len(resultats)
    exacts      = resultats.count("exact")
    sous        = resultats.count("SOUS-TRIAGE")
    sur         = resultats.count("sur-triage")
    sans_triage = resultats.count("aucun triage")

    print("-" * 100)
    print(f"\nBILAN : {exacts}/{total} exacts | {sur} sur-triage | "
          f"{sous} SOUS-TRIAGE | {sans_triage} sans triage")

    if sous > 0:
        print("\n*** ECHEC CRITIQUE : au moins un cas grave a été sous-trié. ***")
        print("*** Ne pas déployer cette version du prompt. ***")
        sys.exit(1)

    print("\nAucun sous-triage : version du prompt acceptable.")
    sys.exit(0)


if __name__ == "__main__":
    main()
