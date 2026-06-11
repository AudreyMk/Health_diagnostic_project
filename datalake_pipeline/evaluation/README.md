# Harness d'évaluation du triage — MedRAG

Ce dossier contient le **crash test** de MedRAG : un jeu de vignettes cliniques
standardisées rejouées automatiquement contre l'API pour mesurer la qualité
du triage.

## Pourquoi

Toute modification du contenu médical (prompts, références cliniques, RAG)
doit être validée AVANT déploiement. La métrique critique est le
**taux de sous-triage** : un cas grave classé bénin est l'erreur qui met
un patient en danger. Le sur-triage (prudence excessive) est acceptable.

Méthodologie inspirée de Semigran et al., BMJ 2015 (45 vignettes, 23 symptom
checkers — voir `../rag_engine/prompts/sources/cliniques/`) et des niveaux
de tri de l'échelle FRENCH (SFMU).

## Fichiers

- `vignettes.json` — 15 faux patients : profil médical, message initial,
  réponses préparées aux questions de l'agent, orientation attendue.
  Inclut 5 vignettes "TERRAIN" qui testent les règles de pondération du
  profil (anticoagulant, asthme, grossesse possible, cardio, diabète).
- `run_eval.py` — joue les vignettes contre l'API locale et affiche le score.

## Utilisation

```bash
# 1. Démarrer les bases (si pas déjà fait)
docker compose up -d

# 2. Démarrer l'API (port 8010)
cd datalake_pipeline
.venv/Scripts/python.exe -m uvicorn rag_engine.api:app --port 8010

# 3. Lancer l'évaluation (dans un autre terminal)
.venv/Scripts/python.exe evaluation/run_eval.py             # tout
.venv/Scripts/python.exe evaluation/run_eval.py --only v01  # une vignette
```

Coût : ~40-60 appels Claude par run complet (quelques minutes).
Les comptes de test `eval_*@medrag.test` sont séparés des vraies données.

## Lire les résultats

| Verdict | Signification | Gravité |
|---|---|---|
| `exact` | Orientation attendue (ou acceptable) | ✅ |
| `sur-triage` | Plus prudent qu'attendu | ⚠️ acceptable, à surveiller |
| `SOUS-TRIAGE` | Moins grave qu'attendu | 🔴 **échec critique — ne pas déployer** |
| `aucun triage` | L'agent n'a pas conclu en 6 tours | ⚠️ à investiguer |

Le script sort en erreur (exit code 1) dès qu'un sous-triage est détecté.

## Règle d'équipe

**Avant tout commit qui modifie `rag_engine/prompts/` :**
1. lancer `run_eval.py` ;
2. noter le score dans le message de commit (ex: `eval: 14/15 exacts, 0 sous-triage`) ;
3. si sous-triage > 0 → corriger avant de committer.

## Journal des runs (référence avant/après chaque modification)

| Date | Version prompts | Score | Sous-triage | Notes |
|------|----------------|-------|-------------|-------|
| 2026-06-10 | system_prompt v2.0 + refs 01-03 | **15/15 exacts** | **0** | Baseline. SAMU détecté en 1 tour sur les 3 cas critiques. Cas terrain : 3× escalade samu au lieu d'urgent (prudent, acceptable). Max 4 tours de questions. |
| 2026-06-10 | + ref 04 (follow-up) + grossesse | **15/15 exacts** | **0** | Après déblocage du suivi. test_follow_up : cliquet + escalade OK. |
| 2026-06-11 | v2.1 questions atomiques + modalité forcée + confirmation positif critique | **8/8 exacts** (v01-v08) | **0** | Correction incident "mal de gorge → SAMU sur tout oui". test_questioning : mal de gorge sans red flag → pharmacien (était samu). v09-v15 NON joués : crédit API Anthropic épuisé (erreur 400 billing, pas une régression). À rejouer en entier après recharge du crédit. |

## Tests ciblés (en plus du harness)

- `test_follow_up.py` — cliquet (ne descend jamais) + escalade sur nouveau red flag.
- `test_questioning.py` — anti faux red flag : un patient qui dit "oui" à tout
  mais sans signe d'alarme réel ne doit PAS être sur-trié. Le harness principal
  tolère le sur-triage par conception, donc ce cas a besoin de son propre test.

### Incident de référence — 2026-06-11
Un mal de gorge fébrile a été trié SAMU parce que l'agent avait posé une
question GROUPÉE (fièvre + respirer + avaler) et accepté un "tout oui" vague.
Correctif : questions atomiques obligatoires, modalité de réponse forcée
(un "oui" ne vaut pas une valeur), confirmation explicite d'un positif critique
avant orientation urgente. Gardé par `test_questioning.py`.

## Faire évoluer le jeu de vignettes

Ajouter une vignette = ajouter un objet dans `vignettes.json` (voir le format
des existantes). Bonnes pratiques :
- couvrir chaque nouvelle règle de pondération par au moins une vignette ;
- ne jamais supprimer une vignette qui a déjà détecté une régression ;
- incrémenter `_version` et dater.
