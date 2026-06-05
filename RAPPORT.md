# 📊 Rapport du projet MedRAG v2

## 1. Vue d'ensemble

**MedRAG v2** est une application web d'**aide au pré-triage médical conversationnel**. L'utilisateur décrit ses symptômes en langage naturel, et un agent IA (Claude) :
1. pose des questions ciblées,
2. interroge une base de connaissances médicales (RAG),
3. propose des hypothèses diagnostiques,
4. recommande une orientation (domicile / pharmacien / médecin / urgent / SAMU),
5. liste les établissements de santé proches du patient.

**⚠️ Disclaimer** : outil d'aide à la décision, ne remplace pas un médecin.

---

## 2. Architecture globale

```
┌────────────────────────┐
│   Frontend React/Vite  │  (port 3000)
│   - Login / Register   │
│   - Chat conversation  │
│   - Carte Leaflet      │
└──────────┬─────────────┘
           │ HTTP/JSON
           ▼
┌────────────────────────┐
│  FastAPI + Uvicorn     │  (port 8000)
│  - Auth (bcrypt)       │
│  - Conversations       │
│  - Chat → Agent Claude │
└──┬──────────────┬──────┘
   │              │
   ▼              ▼
┌──────────┐  ┌──────────┐
│PostgreSQL│  │ MongoDB  │
│+ pgvector│  │ + 2dsphere│
│(:5433)   │  │ (:27018) │
└──────────┘  └──────────┘
```

Tout est containerisé via **Docker Compose** : `postgres`, `mongodb`, `pgadmin` (port 5051), `mongo-express` (port 8082).

---

## 3. Stack technique

| Couche | Technologie |
|---|---|
| Frontend | React 18 + Vite 5 + react-leaflet (cartes) + react-markdown |
| Backend API | FastAPI + Uvicorn + Pydantic |
| Base vectorielle | PostgreSQL 16 + extension `pgvector` (HNSW, distance cosinus) |
| Base NoSQL/géo | MongoDB 7 (index `2dsphere` pour le géospatial) |
| Embeddings | `sentence-transformers` — modèle `intfloat/multilingual-e5-base` (768 dims, FR/EN) |
| LLM | Anthropic `claude-sonnet-4-6` avec **tool use** + **prompt caching** |
| ETL | Python 3.11 + pandas + tqdm + psycopg3 + pymongo |
| Infra | Docker Compose |
| Auth | bcrypt + tokens `secrets.token_hex(32)` (sessions PostgreSQL) |

---

## 4. Pipeline de données (ETL)

### Sources brutes
| Source | Localisation | Volume | Description |
|---|---|---|---|
| **DDXPlus** (Figshare) | [data_brut/20043374/](data_brut/20043374/) | 49 pathologies + ~1,3M patients synthétiques | Dataset bilingue FR/EN, diagnostic différentiel + évidences (symptômes binaires/catégoriques) |
| **MTSamples** | `datalake_pipeline/raw/mtsamples/` | ~5 000 cas cliniques EN | Transcriptions médicales réelles |
| **FINESS** (data.gouv.fr) | téléchargé à la volée | ~2 700 établissements (métropole) | Hôpitaux, cliniques, cabinets, pharmacies — géolocalisés |

### Scripts ETL ([datalake_pipeline/](datalake_pipeline/))

| Script | Rôle | Sortie |
|---|---|---|
| [enrich_pathologies.py](datalake_pipeline/enrich_pathologies.py) | Enrichit DDXPlus avec ICD-11 (API WHO) + Wikipedia FR | `processed/ddxplus_pathology_documents.jsonl` |
| [process_patients.py](datalake_pipeline/process_patients.py) | Sélection stratifiée 50 patients/pathologie (4 tranches d'âge × 2 sexes) | `processed/ddxplus_patient_descriptions.jsonl` |
| [process_mtsamples.py](datalake_pipeline/process_mtsamples.py) | Extraction regex `ASSESSMENT` + `HPI` | `processed/mtsamples_clinical_cases.jsonl` |
| [load_pathologies.py](datalake_pipeline/load_pathologies.py) | Embedding + insertion PostgreSQL (`pathology_documents`) | 49 lignes vectorisées |
| [load_patients.py](datalake_pipeline/load_patients.py) | Idem (`patient_descriptions`) | ~2 450 lignes |
| [load_clinical.py](datalake_pipeline/load_clinical.py) | Idem (`clinical_cases`) | ~4 966 lignes |
| `load_finess.py` | Téléchargement + filtre + insertion MongoDB (`health_centers`) | ~2 700 docs |

Tous les scripts sont **idempotents** (`ON CONFLICT DO UPDATE`).

### Volumétrie finale en base
```json
{
  "pathologies": 49,
  "patients": 2450,
  "clinical_cases": 4966,
  "health_centers": ~2700
}
```

---

## 5. Pipeline RAG ([datalake_pipeline/rag_engine/](datalake_pipeline/rag_engine/))

### 5.1 Retrieval — 3 pools sémantiques en parallèle

| Pool | Table PostgreSQL | Fonction SQL | Top-K | Filtre |
|---|---|---|---|---|
| **1. Pathologies** | `pathology_documents` | `search_pathologies()` | 4 | similarité ≥ 0.25 |
| **2. Patients similaires** | `patient_descriptions` | `search_similar_patients()` | 3 | + âge ±15 ans, sexe |
| **3. Cas cliniques réels** | `clinical_cases` | `search_clinical_cases()` | 2 | similarité ≥ 0.25 |

+ **Pool géospatial MongoDB** : `health_centers` filtrés par département pour proposer des établissements réels au patient.

Le score de similarité est `1 - (embedding <=> query)` via pgvector.
Les requêtes sont préfixées par `"query: "` et les passages par `"passage: "` (exigence du modèle e5).

### 5.2 Agent LLM — Claude avec Tool Use ([llm_client.py](datalake_pipeline/rag_engine/llm_client.py))

C'est le cœur "intelligent" du système. Au lieu de toujours faire un RAG, **Claude décide lui-même** quand interroger la base.

**Outil exposé à Claude** :
```python
{
  "name": "chercher_informations_medicales",
  "input_schema": { "symptomes": str }
}
```

**Boucle agentique** :
1. Claude reçoit l'historique + le system prompt.
2. Si `stop_reason == "tool_use"` → l'API exécute `_execute_search()` (les 3 pools + MongoDB) et renvoie le résultat à Claude.
3. La boucle continue jusqu'à ce que Claude produise sa réponse finale.

**Sortie structurée obligatoire** (parsée par l'API) :
```
**Synthèse**
**Pathologies possibles**
**⚠️ Signes d'alarme**
**Orientation recommandée**
**Structures de santé dans votre secteur**
<TRIAGE>{"orientation":"medecin","color":"orange","hypotheses":[...],"summary":"..."}</TRIAGE>
```

**Optimisation** : `cache_control: ephemeral` sur le system prompt → coût et latence réduits sur les conversations longues.

---

## 6. API FastAPI ([api.py](datalake_pipeline/rag_engine/api.py))

### Authentification ([auth.py](datalake_pipeline/rag_engine/auth.py))
| Endpoint | Méthode | Description |
|---|---|---|
| `/auth/register` | POST | Création compte (mot de passe **bcrypt**, id = UUID4) |
| `/auth/login` | POST | Renvoie un token de session (`secrets.token_hex(32)`) |
| `/auth/me` | GET | Valide le token Bearer |
| `/auth/profile` | PUT | Met à jour le département du user |

### Conversations ([conversation.py](datalake_pipeline/rag_engine/conversation.py))
| Endpoint | Méthode | Description |
|---|---|---|
| `/conversations` | POST | Crée une nouvelle conversation |
| `/conversations` | GET | Liste les 20 dernières |
| `/conversations/{id}/messages` | GET | Charge l'historique |
| `/conversations/{id}/chat` | POST | Envoie un message → réponse + bloc `triage` parsé |

### Autres
| Endpoint | Méthode | Description |
|---|---|---|
| `/centers?dept=XX` | GET | Liste FINESS du département |
| `/health` | GET | Statistiques système |

Toutes les routes sauf `/auth/*` et `/health` exigent un header `Authorization: Bearer <token>`.

---

## 7. Schéma des bases de données

### PostgreSQL ([init-postgres.sql](datalake_pipeline/docker/init-postgres.sql))
- **Tables RAG** : `pathology_documents`, `patient_descriptions`, `clinical_cases` (toutes avec colonne `embedding vector(768)`)
- **Tables app** : `users`, `sessions`, `conversations`, `conversation_messages`
- **Audit** : `query_logs` (traçabilité requise en contexte médical : query, age, sex, triage_level, response_time)
- **Fonctions PL/pgSQL** : 3 fonctions `search_*` qui encapsulent la similarité cosinus et les filtres

### MongoDB ([init-mongo.js](datalake_pipeline/docker/init-mongo.js))
- `health_centers` — index `2dsphere` (`location`), index texte (nom/ville), index par département/catégorie
- `recommendations_log` — TTL 30 jours

---

## 8. Frontend ([frontend/](frontend/))

### Composants
| Fichier | Rôle |
|---|---|
| [LoginPage.jsx](frontend/src/LoginPage.jsx) | Onglets connexion / inscription |
| [App.jsx](frontend/src/App.jsx) | Shell : sidebar conversations, chat, results panel |
| `ResultsPanel.jsx` | Carte Leaflet + liste FINESS triés par distance (Haversine) |

### Fonctionnalités UX
- **Géolocalisation navigateur** → reverse-geocoding via Nominatim (OpenStreetMap) → extraction du département → enregistré côté API.
- **Markdown rendering** des réponses Claude.
- **Layout responsive** : 2 colonnes desktop (chat + résultats), toggle mobile.
- **Persistance** : token + user en `localStorage`.
- **Vite proxy** : `/api/*` → `http://localhost:8000` (évite les soucis CORS en dev).

### Design
CSS pur, palette : vert `#0d7c66` (brand), gris `#a0aec0`, fond beige `#f7fafc`. Bulles asymétriques bot / user.

---

## 9. Fonctionnalités clés de l'outil

1. **Conversation multi-tours** avec mémoire (Claude voit tout l'historique sauvegardé en base).
2. **Triage médical structuré** en 5 niveaux avec code couleur (vert → rouge).
3. **Hypothèses diagnostiques** classées par confiance, basées sur des cas réels (DDXPlus + MTSamples).
4. **Personnalisation démographique** : le pool 2 filtre les patients similaires par âge ±15 ans et sexe.
5. **Recommandation géolocalisée** : établissements FINESS réels du département du patient.
6. **Multilingue** (modèle e5 + Claude) : l'utilisateur peut écrire en français même si la base MTSamples est en anglais.
7. **Authentification sécurisée** : bcrypt + tokens session.
8. **Auditabilité** : table `query_logs` (exigence en contexte santé).

---

## 10. Points forts techniques

- **Embeddings multilingues** avec préfixes `query:` / `passage:` (best practice e5).
- **Tool use Claude** : l'agent décide quand faire le RAG, plutôt qu'un RAG systématique → conversations plus naturelles.
- **Prompt caching** Anthropic : économies sur les longues conversations.
- **3 pools sémantiques séparés** : permet de pondérer indépendamment les sources (théorie / cas patients / cas cliniques).
- **Index pgvector HNSW** : recherche en O(log n), scalable au-delà de centaines de milliers de docs.
- **Architecture services indépendants** : ETL, API, Frontend découplés.

---

## 11. Limites & axes d'amélioration

- CORS `allow_origins=["*"]` → à restreindre en prod.
- Pas de TTL sur les tokens de session.
- Le dossier `raw/finess/` est vide → re-téléchargé dynamiquement (lent au premier run).
- Pas de tests automatisés visibles.
- Anglais/français mélangés dans MTSamples — un re-ranker ou une traduction améliorerait la qualité.
- L'`age_group` et la sévérité (1–5) sont peu exploités côté triage final.
