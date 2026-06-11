# Traçabilité des sources cliniques et réglementaires — MedRAG

Chaque contenu clinique injecté dans les prompts doit être relié à une source
officielle listée ici. Les documents téléchargés sont stockés dans ce dossier
(`prompts/sources/`) comme preuve documentaire — ils ne sont PAS injectés
dans les prompts.

## Où stocker les téléchargements

```
prompts/sources/
├── SOURCES.md           ← ce fichier (l'index — tenir à jour les statuts)
├── cliniques/           ← sections A (§1 à §6) : HAS, SFMU, NICE, BMJ...
└── reglementaires/      ← sections B (§7 à §10) : MDR, MDCG, CNIL, HDS...
```

Convention de nommage : `ORGANISME_sujet_annee.pdf` en minuscules sans espaces.
Exemples :
- `cliniques/has_lombalgie_commune_2019.pdf`
- `cliniques/sfmu_echelle_tri_french.pdf`
- `reglementaires/mdcg_2019-11_software_qualification.pdf`
- `reglementaires/cnil_referentiel_donnees_sante.pdf`

Après chaque téléchargement : passer le statut de ⬜ à ✅ ci-dessous et
ajouter une ligne au journal des modifications en bas de ce fichier.

Statut : ⬜ à télécharger · ✅ téléchargé · 💰 payant (à budgéter) · 📖 domaine public (pas de PDF unique à archiver)

---

## A. Sources cliniques (alimentent les fichiers references/)

### §1 — Cadres d'anamnèse (→ 01_anamnese_socrates.md)
- 📖 **SOCRATES** : mnémonique d'anamnèse de la douleur, domaine public
  (enseignement médical international, enseigné dans toutes les facultés
  de médecine). Pas de PDF unique à archiver — référençable via n'importe
  quel manuel de sémiologie ou cours universitaire en accès libre.
- 📖 **OPQRST** : équivalent en médecine d'urgence — même statut.

### §2 — Recommandations HAS (→ 02_red_flags + 03_ponderation) — GRATUIT
- ✅ « Lombalgie commune » (2019) — fiche mémo + rapport + arbre décisionnel :
  `cliniques/has_lombalgie_*.pdf` → red flags dos (queue de cheval, fracture,
  infection, cancer).
- ✅ « Fièvre chez l'enfant » (fiche mémo) : `cliniques/has_fievre_enfant_fiche_memo.pdf`
- ✅ « Évaluation du pied d'un patient diabétique » (fiche outil) :
  `cliniques/has_pied_diabetique_fiche_evaluation.pdf` → règle pondération diabète.
- ✅ PNDS « Syndromes drépanocytaires majeurs enfant/adolescent » + argumentaire :
  `cliniques/has_pnds_drepanocytose_*.pdf` → future règle de pondération
  (drépanocytose : fièvre ou douleur = urgence, jamais domicile).
- ⬜ Autres fiches « Pertinence des soins » au fur et à mesure des besoins.
- ✅ « Prise en charge du sepsis du nouveau-né, de l'enfant et de l'adulte »
  (HAS + 17 sociétés savantes, validée janvier 2025) :
  `cliniques/has_reco_sepsis_2025.pdf` + argumentaire + fiches parcours
  amont/aval. → source officielle de la ligne "Fièvre → sepsis" du fichier
  02_red_flags. La fiche AMONT (reconnaissance pré-hospitalière des signes)
  correspond exactement au cas d'usage MedRAG.

### §3 — Échelle de tri FRENCH — SFMU — GRATUIT
- ✅ « Échelle de tri FRENCH » v1.2 (déc. 2019) :
  `cliniques/sfmu_echelle_tri_french_v1-2_2019.pdf`
  LA référence française officielle des niveaux de tri aux urgences.
  → justifie la correspondance entre nos 5 orientations
  (domicile/pharmacien/médecin/urgent/samu) et les niveaux de tri reconnus.

### §4 — Red flags par présentation — NICE CKS (UK) — GRATUIT
- ⬜ NICE Clinical Knowledge Summaries (cks.nice.org.uk) — fiches red flags
  par symptôme (headache, chest pain, abdominal pain…). En anglais, accès
  libre, référence internationale. Sert de vérification croisée des fiches HAS.

### §5 — Référence du tri téléphonique — 💰 PAYANT (fortement recommandé)
- 💰 « Guide d'aide à la régulation au SAMU Centre 15 » (SFEM éditions,
  3e édition). C'est l'ouvrage de référence français du tri médical à
  distance — le cas d'usage le plus proche de MedRAG. ~80-100 €.
  → À budgéter en priorité : c'est la source qui crédibilise le plus la
  démarche de triage auprès d'investisseurs et de partenaires médicaux.

### §6 — Sources pour le futur pool RAG guidelines (phase 3 roadmap)
- ⬜ Fiches Ameli santé (ameli.fr) — vocabulaire patient, accès libre.
- 💰 SFMG — Dictionnaire des Résultats de Consultation (DRC) — abonnement.
- 💰 Vidal — API/licence pour les interactions médicamenteuses (négociation).

---

## B. Sources réglementaires (alimentent le RAPPORT, pas les prompts)

### §7 — Dispositif médical logiciel — GRATUIT
- ✅ **Règlement (UE) 2017/745 (MDR)** — texte intégral FR :
  `reglementaires/eu_mdr_2017-745_fr.pdf`
  Règle 11 de l'annexe VIII = qualification des logiciels d'aide à la décision.
- ✅ **MDCG 2019-11** « Guidance on Qualification and Classification of
  Software » : `reglementaires/mdcg_2019-11_software_qualification.pdf`
  LE document qui explique si/comment un logiciel comme MedRAG est qualifié
  DM et sa classe.
- ✅ ANSM — lot complet « logiciels et applications mobiles en santé » :
  `reglementaires/ansm_*.pdf` (8 fiches : statut DM, qualification et marche
  à suivre, classification, cybersécurité, traçabilité, dispositions
  transitoires). La fiche `ansm_exemples_positionnement_reglementaire.pdf`
  donne des exemples concrets de logiciels qualifiés DM ou non — document
  clé pour argumenter le statut de MedRAG dans le rapport.

### §8 — RGPD / données de santé
- ⬜ CNIL — les référentiels eux-mêmes (PDF) : durées de conservation santé,
  cabinets médicaux. ⚠️ Seules les PAGES D'INDEX ont été téléchargées
  (`cnil_index_referentiels_sante_2023.pdf` — contient les liens vers les
  référentiels à récupérer).
- ✅ CNIL — guides AIPD complets : `reglementaires/cnil_pia_1_methode.pdf`
  + modèles + bases de connaissances + exemple appliqué
  + « Ce qu'il faut savoir sur l'AIPD » + liste des traitements dispensés
  + fiche « IA : réaliser une analyse d'impact » (pertinente pour un outil
  IA santé) + « Sécurité : analyse de risques ».
- ✅ Référentiel **certification HDS v2** (ANS) :
  `reglementaires/ans_referentiel_certification_hds_v2.pdf`
  + référentiel d'accréditation + communiqué officiel (mai 2024).
  Note utile pour le rapport : les hébergeurs certifiés v1 doivent migrer
  vers la v2 au plus tard le 16 mai 2026 → choisir directement un hébergeur
  certifié v2.

### §9 — Normes qualité logiciel DM — 💰 PAYANT (citer sans acheter pour l'instant)
- 💰 **IEC 62304** — cycle de vie logiciel dispositif médical (~200 € AFNOR).
- 💰 **ISO 14971** — gestion des risques dispositifs médicaux.
- 💰 **ISO 13485** — système de management qualité DM.
  → Pour le rapport de levée de fonds : il suffit de citer ces normes et de
  montrer que l'architecture est conçue pour s'y conformer (traçabilité des
  prompts, versionnage, harness d'évaluation). L'achat se fera avec les fonds.

### §10 — Évaluation des symptom checkers (pour le harness de vignettes)
- ✅ Semigran et al., « Evaluation of symptom checkers for self diagnosis and
  triage: audit study », BMJ 2015 :
  `cliniques/bmj_semigran_symptom_checkers_2015.pdf`
  Fournit la méthodologie des 45 vignettes cliniques standardisées (3 niveaux
  d'urgence : urgent / non-urgent / auto-soins), base de notre jeu de test.

---

## Journal des modifications

| Date | Fichier impacté | Modification | Source |
|------|----------------|--------------|--------|
| 2026-06-10 | Création initiale du dossier | v1.0 de toutes les références | Audit adversarial pipeline |
| 2026-06-10 | sources/ | 1er lot téléchargé : MDR, MDCG 2019-11, HDS v2 (×2 + CP), BMJ Semigran 2015, sepsis HAS 2025 (×4), index CNIL (×2) | Téléchargements officiels |
| 2026-06-10 | sources/ | 2e lot : échelle FRENCH (SFMU), lombalgie HAS (×4), fièvre enfant, pied diabétique, PNDS drépanocytose (×2), ANSM (×8), CNIL PIA/AIPD (×8) | Téléchargements officiels |
