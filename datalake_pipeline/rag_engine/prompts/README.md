# Dossier prompts — MedRAG

Ce dossier contient **tout le contenu textuel injecté dans les appels Claude**.
Aucun prompt ne doit être écrit en dur dans le code Python : `llm_client.py`
charge ces fichiers via `prompts.py`.

## Structure

```
prompts/
├── README.md                    ← ce fichier
├── system_prompt.md             ← prompt principal de l'agent conversationnel
├── report_prompt.md             ← prompt d'extraction de la fiche pré-consultation
├── references/                  ← connaissances cliniques INJECTÉES dans le system prompt
│   ├── 01_anamnese_socrates.md      (cadre de recueil des symptômes)
│   ├── 02_red_flags_must_not_miss.md (diagnostics à ne jamais manquer)
│   ├── 03_ponderation_profil.md     (règles de pondération selon le profil patient)
│   └── 04_follow_up_rules.md        (suivi post-orientation : cliquet, re-scan red flags)
└── sources/
    └── SOURCES.md               ← traçabilité : d'où vient chaque contenu clinique
                                   (+ les PDF officiels téléchargés, non injectés)
```

## Règles de mise à jour (exigence réglementaire — traçabilité)

1. **Chaque fichier porte un en-tête** `Version` + `Date` + `Sources`.
   Toute modification = incrémenter la version + dater + noter le motif.
2. **Les fichiers `references/` sont injectés dans l'ordre de leur numéro**
   (01, 02, 03...). Ajouter une référence = créer `04_xxx.md`, elle sera
   chargée automatiquement, sans toucher au code.
3. **Le dossier `sources/` contient les documents officiels d'origine**
   (PDF HAS, SFMU, etc.). Ils ne sont PAS injectés dans le prompt — ils
   servent de preuve documentaire pour le rapport et les audits.
4. **Avant tout déploiement d'une modification de prompt** : rejouer le jeu
   de vignettes cliniques de test (harness d'évaluation) et vérifier que le
   taux de sous-triage n'a pas augmenté.

## Pourquoi cette architecture (à reprendre dans le rapport)

- **Traçabilité** : chaque affirmation clinique du prompt est reliée à une
  source officielle identifiée (SOURCES.md) — exigence des référentiels
  qualité logiciels dispositifs médicaux (IEC 62304, gestion de configuration).
- **Maintenabilité** : une recommandation HAS mise à jour = modifier un
  fichier markdown, pas le code.
- **Auditabilité** : l'historique git du dossier = le journal des
  modifications du contenu médical de l'outil.
