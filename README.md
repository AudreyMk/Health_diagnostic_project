<div align="center">

# 🩺 MedRAG

**Outil d'aide à la décision clinique basé sur RAG**  
*Projet M2 Data Science — Université*

[![Pipeline](https://gitlab.com/kamkamgaing-group/projet_medrag/badges/main/pipeline.svg)](https://gitlab.com/kamkamgaing-group/projet_medrag/-/pipelines)
[![Coverage](https://gitlab.com/kamkamgamgaing-group/projet_medrag/badges/main/coverage.svg)](https://gitlab.com/kamkamgaing-group/projet_medrag/-/pipelines)

</div>

---

## 📋 Table des matières

1. [Vue d'ensemble](#-vue-densemble)
2. [Architecture](#-architecture)
3. [Données](#-données)
4. [Prérequis](#-prérequis)
5. [Installation & Lancement](#-installation--lancement)
6. [Utilisation de l'interface](#-utilisation-de-linterface)
7. [API REST](#-api-rest)
8. [Pipeline CI/CD](#-pipeline-cicd)
9. [Structure du projet](#-structure-du-projet)
10. [Avertissement médical](#️-avertissement-médical)

---

## 🔍 Vue d'ensemble

MedRAG est un système de **Retrieval-Augmented Generation (RAG)** médical qui :

1. Prend en entrée une **description de symptômes en langage naturel**
2. Recherche les **pathologies et cas patients similaires** par similarité sémantique (pgvector)
3. Localise les **établissements de santé proches** via géolocalisation (MongoDB)
4. Génère des **hypothèses diagnostiques structurées** avec Claude (Anthropic)

> ⚠️ Cet outil est destiné aux **professionnels de santé** comme aide à la décision. Il ne remplace pas un diagnostic médical.

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Interface React                        │
│   Formulaire symptômes │ Résultats │ Carte Leaflet (FINESS) │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP / JSON
┌────────────────────────▼────────────────────────────────────┐
│                    FastAPI — port 8000                       │
│   POST /api/suggest   GET /api/health   GET /api/pathologies │
└──────────┬──────────────────────────────────────┬───────────┘
           │                                      │
┌──────────▼──────────────┐        ┌──────────────▼──────────┐
│  EmbeddingManager        │        │  MongoRetriever          │
│  multilingual-e5-base    │        │  Centres FINESS          │
│  (768 dims, query: )     │        │  Index 2dsphere $near    │
└──────────┬──────────────┘        └──────────────────────────┘
           │ vecteur requête
┌──────────▼──────────────┐        ┌──────────────────────────┐
│  PGRetriever             │   ───▶ │  LLMClient               │
│  PostgreSQL + pgvector   │  docs  │  Claude claude-sonnet-4-6│
│  search_similar_docs()   │        │  + prompt caching        │
│  Index HNSW cosinus      │        └──────────────────────────┘
└─────────────────────────┘
```

### Stack technique

| Composant | Technologie | Rôle |
|---|---|---|
| Frontend | React 18 + Vite + Leaflet | Interface utilisateur |
| API | FastAPI + Uvicorn | Serveur REST |
| Embedding | `intfloat/multilingual-e5-base` | Encodage sémantique (768 dims) |
| Retrieval | PostgreSQL 16 + pgvector | Similarité cosinus, index HNSW |
| Géospatial | MongoDB 7 | Centres de santé FINESS, index 2dsphere |
| LLM | Claude `claude-sonnet-4-6` | Génération des hypothèses diagnostiques |
| Infra | Docker Compose | Orchestration des services |
| CI/CD | GitLab CI | Tests, build Docker, déploiement |

---

## 📊 Données

| Source | Description | Volume |
|---|---|---|
| **DDXPlus FR** | Dataset synthétique de pathologies (Figshare) | 49 pathologies, ~1,3M patients |
| **FINESS** | Établissements de santé français (data.gouv.fr) | ~52 000 centres géolocalisés |
| **CSV médical** | Descriptions symptômes/pathologies (anglais) | 5 580 entrées, 27 pathologies |

Les données sont stockées dans `datalake_pipeline/processed/` après traitement (voir [Pipeline de données](#pipeline-de-données)).

---

## ✅ Prérequis

- **Docker Desktop** — [Télécharger](https://www.docker.com/products/docker-desktop/)
- **Node.js 20+** — [Télécharger](https://nodejs.org/)
- **Python 3.11+** — [Télécharger](https://www.python.org/)
- **Clé API Anthropic** — [Créer un compte](https://console.anthropic.com/) *(optionnel pour le retrieval seul)*

---

## 🚀 Installation & Lancement

### 1. Cloner le projet

```bash
git clone https://gitlab.com/kamkamgaing-group/projet_medrag.git
cd projet_medrag
```

### 2. Configurer l'environnement

```bash
cd datalake_pipeline
cp .env.example .env
```

Éditez `.env` et renseignez votre clé Anthropic :

```env
ANTHROPIC_API_KEY=sk-ant-...   # obligatoire pour les suggestions LLM
```

### 3. Démarrer l'infrastructure (bases de données)

```bash
# Depuis datalake_pipeline/
docker compose up -d postgres mongodb pgadmin mongo-express
```

Vérifiez que les conteneurs sont **healthy** :

```bash
docker ps
```

```
NAMES                  STATUS
medrag-postgres        Up (healthy)   ← PostgreSQL + pgvector
medrag-mongodb         Up (healthy)   ← MongoDB
medrag-pgadmin         Up             ← Interface admin PG
medrag-mongo-express   Up             ← Interface admin Mongo
```

### 4. Charger les données (première fois uniquement)

```bash
# Créer et activer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate          # Linux/Mac
# .venv\Scripts\activate           # Windows

# Installer les dépendances
pip install -r requirements.txt -r requirements_rag.txt

# Importer les données + vectoriser avec sentence-transformers
python load_to_databases.py
```

> ⏳ La vectorisation de 43 000+ patients prend ~10-20 min selon votre machine.

### 5. Lancer l'API

```bash
# Depuis datalake_pipeline/ (venv activé)
uvicorn rag_engine.api:app --host 0.0.0.0 --port 8000 --reload
```

### 6. Lancer l'interface React

```bash
# Nouveau terminal, depuis frontend/
npm install
npm run dev
```

### ✅ L'application est disponible

| Service | URL | Identifiants |
|---|---|---|
| **Interface MedRAG** | http://localhost:3000 | — |
| **API Swagger** | http://localhost:8000/docs | — |
| **pgAdmin** | http://localhost:5050 | admin@medrag.com / admin |
| **Mongo Express** | http://localhost:8081 | admin / admin |

---

## 🖥 Utilisation de l'interface

### Panneau gauche — Saisie

1. **Symptômes** : décrivez les symptômes en texte libre (français de préférence)
   > *Ex : "Fièvre à 39°C depuis 3 jours, toux sèche, douleurs thoraciques, fatigue"*

2. **Informations patient** : âge et sexe (optionnels, améliorent la précision)

3. **Localisation** : cliquez sur **"Ma position GPS"** ou directement sur la carte pour activer la recherche de centres proches. Ajustez le rayon avec le curseur.

4. Cliquez sur **"Analyser les symptômes"**

### Panneau droit — Carte interactive

- **Point bleu pulsant** : votre position
- **Points colorés** : établissements de santé FINESS trouvés dans le rayon
  - 🔴 CHU / CHR
  - 🟠 Centre Hospitalier
  - 🟡 Clinique
  - 🟢 Maison de santé
  - 🔵 Pharmacie / Laboratoire
- **Clic sur un marqueur** : nom, adresse, téléphone, catégorie

### Résultats

- **Analyse IA** : hypothèses diagnostiques générées par Claude avec justification
- **Pathologies similaires** : classées par score de similarité sémantique avec barre de confiance
- **Établissements proches** : affichés sur la carte avec détails au clic

---

## 📡 API REST

### `POST /api/suggest` — Suggestion de pathologies

```bash
curl -X POST http://localhost:8000/api/suggest \
  -H "Content-Type: application/json" \
  -d '{
    "symptoms": "Fièvre à 39°C, toux sèche, douleurs thoraciques",
    "age": 45,
    "sex": "M",
    "latitude": 48.8566,
    "longitude": 2.3522,
    "max_distance_km": 10,
    "top_k": 8,
    "min_similarity": 0.25
  }'
```

<details>
<summary>Exemple de réponse</summary>

```json
{
  "query": "Fièvre à 39°C, toux sèche, douleurs thoraciques",
  "patient_info": { "age": 45, "sex": "M" },
  "pathologies_retrieved": [
    {
      "id": "patho_...",
      "pathology": "Pneumonie",
      "text": "Pathologie : Pneumonie. Code CIM-10 : J18...",
      "similarity": 0.84
    }
  ],
  "nearby_centers": [ { "name": "CHU Paris...", "category": "CHU", ... } ],
  "llm_response": "## Analyse clinique\n...",
  "performance": { "total_seconds": 1.4 },
  "retrieval_stats": { "pathologies_found": 5, "top_similarity": 0.84 }
}
```
</details>

### `GET /api/health` — État de l'API

```bash
curl http://localhost:8000/api/health
```

### `GET /api/pathologies` — Liste des pathologies indexées

```bash
curl http://localhost:8000/api/pathologies
```

### `POST /api/centers` — Centres de santé proches

```bash
curl -X POST http://localhost:8000/api/centers \
  -H "Content-Type: application/json" \
  -d '{ "latitude": 48.8566, "longitude": 2.3522, "max_distance_km": 5 }'
```

📖 Documentation interactive complète : **http://localhost:8000/docs**

---

## 🔄 Pipeline CI/CD

Le pipeline GitLab CI s'exécute automatiquement à chaque push.

```
push
  │
  ├── lint
  │     ├── backend:lint     → ruff (qualité Python)
  │     └── frontend:lint    → vite build (vérifie le frontend)
  │
  ├── test
  │     └── backend:unit-tests → 32 tests pytest (couverture de code)
  │
  ├── build  (main / develop uniquement)
  │     ├── api:docker-build   → image Docker → GitLab Registry
  │     └── frontend:build-prod → bundle React (artifact)
  │
  └── deploy  (main, déclenchement manuel)
        └── deploy:staging   → SSH + docker compose pull + restart
```

### Configurer les variables GitLab

`Settings → CI/CD → Variables` :

| Variable | Description | Masquée |
|---|---|---|
| `ANTHROPIC_API_KEY` | Clé API Anthropic | ✅ |
| `SSH_PRIVATE_KEY` | Clé SSH pour le serveur staging | ✅ |
| `STAGING_HOST` | IP ou hostname du serveur | ❌ |
| `STAGING_USER` | Utilisateur SSH | ❌ |

### Lancer les tests localement

```bash
cd datalake_pipeline
pip install -r requirements_dev.txt
pytest tests/ -v --cov=rag_engine
```

---

## 📁 Structure du projet

```
projet_medrag/
│
├── .gitlab-ci.yml                 ← Pipeline CI/CD GitLab
├── pyproject.toml                 ← Config ruff + pytest
├── .gitignore
├── README.md
├── combined_medical_data.csv      ← Source données CSV
│
├── frontend/                      ← Interface React
│   ├── src/
│   │   ├── App.jsx                ← Layout principal + gestion d'état
│   │   ├── index.css              ← Styles (dark theme, animations)
│   │   └── components/
│   │       ├── SymptomForm.jsx    ← Formulaire symptômes + GPS
│   │       ├── ResultsPanel.jsx   ← Résultats LLM + cartes pathologies
│   │       └── HospitalMap.jsx    ← Carte Leaflet + marqueurs FINESS
│   ├── package.json
│   └── vite.config.js             ← Proxy → API port 8000
│
└── datalake_pipeline/             ← Backend + pipeline data
    │
    ├── rag_engine/                ← Cœur du système RAG
    │   ├── config.py              ← Variables d'environnement
    │   ├── embedding_manager.py   ← Encodage requêtes (e5-base)
    │   ├── retriever.py           ← pgvector + MongoDB $near
    │   ├── llm_client.py          ← Claude API + prompt caching
    │   ├── rag_engine.py          ← Orchestrateur du pipeline
    │   └── api.py                 ← Endpoints FastAPI
    │
    ├── tests/                     ← Tests unitaires
    │   ├── conftest.py            ← Fixtures + mock dépendances lourdes
    │   ├── test_api.py            ← 20 tests endpoints FastAPI
    │   ├── test_embedding.py      ← 3 tests EmbeddingManager
    │   └── test_retriever.py      ← 9 tests PGRetriever + MongoRetriever
    │
    ├── docker/
    │   ├── init-postgres.sql      ← Schéma PG + fonction search_similar_documents()
    │   └── init-mongo.js          ← Index 2dsphere + collections MongoDB
    │
    ├── processed/                 ← Données JSONL (gitignorées)
    │   ├── ddxplus_pathology_documents.jsonl
    │   ├── ddxplus_patient_descriptions.jsonl
    │   ├── finess_health_centers.jsonl
    │   └── csv_symptom_descriptions.jsonl
    │
    ├── ingest_to_s3.py            ← Ingestion AWS S3 (DDXPlus, FINESS, CSV)
    ├── unified_data_processor.py  ← Traitement + normalisation JSONL
    ├── load_to_databases.py       ← Import PG + MongoDB + vectorisation
    ├── docker-compose.yml         ← Services : PG, MongoDB, pgAdmin, API
    ├── Dockerfile                 ← Image Docker de l'API RAG
    ├── requirements.txt           ← Dépendances pipeline data
    ├── requirements_rag.txt       ← Dépendances RAG engine
    ├── requirements_dev.txt       ← Dépendances développement + tests
    └── .env.example               ← Template de configuration
```

---

## Pipeline de données (réingestion)

Si vous souhaitez régénérer les données depuis les sources :

```bash
# Étape 1 — Ingestion depuis les sources publiques vers AWS S3
python ingest_to_s3.py --sources ddxplus finess csv

# Étape 2 — Traitement et normalisation
python unified_data_processor.py \
  --ddxplus-conditions raw/ddxplus/release_conditions.json \
  --ddxplus-evidences  raw/ddxplus/release_evidences.json \
  --ddxplus-patients   raw/ddxplus/release_train_patients.csv \
  --finess-etab        raw/finess/finess_etablissements.csv \
  --csv-symptoms       ../combined_medical_data.csv \
  --output-dir         ./processed \
  --max-patients       100000

# Étape 3 — Import bases de données + vectorisation
python load_to_databases.py
```

---

## ⚠️ Avertissement médical

> MedRAG est un **outil d'aide à la décision clinique** destiné aux professionnels de santé.  
> Il ne remplace en aucun cas l'évaluation d'un médecin qualifié.  
> Les données DDXPlus utilisées sont **synthétiques** et ne proviennent pas de cas réels.  
> **Tout diagnostic doit être posé par un professionnel de santé après examen clinique.**

---

<div align="center">
Projet M2 Data Science · GitLab CI/CD · RAG · pgvector · MongoDB · Claude API
</div>
