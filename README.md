# MedRAG v2

Assistant web de pre-consultation medicale base sur une architecture RAG (Retrieval-Augmented Generation).

Ce projet aide le patient a structurer ses symptomes, detecter les signes d'alerte, preparer une consultation et orienter vers le bon niveau de soin. Il ne remplace pas un professionnel de sante.

## Vue d'ensemble

MedRAG v2 combine :

- un backend FastAPI pour l'authentification, les conversations et le triage ;
- un moteur RAG multi-sources (pathologies, patients similaires, cas cliniques, FINESS) ;
- une interface web principale Next.js (`med-rag-product-ux`) ;
- une interface React/Vite historique (`frontend`) conservee pour prototypage.

## Stack technique

- Frontend principal : Next.js 16, React 19, TypeScript, composants UI Radix/Shadcn
- Frontend legacy : React 18 + Vite
- Backend API : FastAPI + Uvicorn
- LLM : Anthropic Claude (`claude-sonnet-4-6` par defaut)
- Embeddings : `intfloat/multilingual-e5-base`
- Retrieval semantique : PostgreSQL 16 + pgvector
- Geo-recherche : MongoDB 7 (index 2dsphere FINESS)
- Orchestration locale : Docker Compose

## Architecture (v2)

1. Le patient cree un compte puis complete son onboarding medical.
2. Le frontend appelle les routes `/api/*` du backend FastAPI.
3. Le backend charge l'historique de conversation + profil patient.
4. Claude peut appeler un outil de recherche interne pour interroger :
   - pool 1 : pathologies
   - pool 2 : patients similaires
   - pool 3 : cas cliniques
   - etablissements FINESS
5. Le backend applique les garde-fous de triage (regle de cliquet), persiste conversation, triage et fiche pre-consultation.

## Arborescence utile

```text
projet_medrag_v2/
   datalake_pipeline/
      rag_engine/
         api.py
         llm_client.py
         retriever.py
         auth.py
         conversation.py
         patient_profile.py
      docker-compose.yml
      load_pathologies.py
      load_patients.py
      load_clinical.py
      load_finess.py
      evaluation/
   med-rag-product-ux/   # frontend principal
   frontend/             # frontend legacy
   docs/SETUP.md
   README.md
```

## Prerequis

- Docker Desktop
- Python 3.11+
- Node.js 20+
- Cle API Anthropic

## Installation rapide (Windows)

### 1) Cloner le projet

```powershell
git clone <URL_DU_DEPOT> projet_medrag_v2
cd projet_medrag_v2
```

### 2) Lancer les bases (Docker)

```powershell
cd datalake_pipeline
docker compose up -d
```

Services demarres :

- PostgreSQL : `localhost:5433`
- MongoDB : `localhost:27018`
- pgAdmin : `http://localhost:5051`
- Mongo-Express : `http://localhost:8082`

### 3) Configurer Python

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 4) Configurer les variables d'environnement

```powershell
copy .env.example .env
```

Renseigner au minimum dans `.env` :

```env
ANTHROPIC_API_KEY=sk-ant-...
```

### 5) Charger les donnees

```powershell
python load_pathologies.py
python load_patients.py
python load_clinical.py
python load_finess.py
```

### 6) Lancer l'API

```powershell
python -m uvicorn rag_engine.api:app --host 0.0.0.0 --port 8000 --reload
```

API disponible sur : `http://localhost:8000`

### 7) Lancer le frontend principal

Dans un nouveau terminal :

```powershell
cd med-rag-product-ux
npm install
npm run dev
```

Application web : `http://localhost:3000`

Le proxy Next.js redirige `/api/*` vers `http://localhost:8000/api/*`.

## Endpoints API principaux

Toutes les routes sont prefixees par `/api`.

### Authentification et profil utilisateur

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `PUT /api/auth/profile`

### Profil medical patient

- `GET /api/patient/profile`
- `POST /api/patient/profile`

### Conversations et triage

- `POST /api/conversations`
- `GET /api/conversations`
- `GET /api/conversations/{conv_id}/messages`
- `POST /api/conversations/{conv_id}/chat`
- `GET /api/conversations/{conv_id}/report`
- `GET /api/conversations/{conv_id}/triage`

### Etablissements et sante systeme

- `GET /api/centers`
- `GET /api/health`

## Evaluation

Scripts disponibles dans `datalake_pipeline/evaluation/` :

```powershell
python evaluation\run_eval.py
python evaluation\test_follow_up.py
python evaluation\test_questioning.py
```

## Notes importantes

- Les fichiers `datalake_pipeline/processed/*.jsonl` peuvent ne pas etre versionnes selon votre setup.
- La cle Anthropic est indispensable pour les reponses conversationnelles LLM.
- La regle de securite medicale est stricte : triage avec cliquet (pas de retrogradation automatique).

## Documentation complementaire

- Guide d'installation detaille : `docs/SETUP.md`
- Contexte produit et contraintes medicales : `CLAUDE.md`
- Schema SQL : `docs/schema.sql`

## Avertissement medical

Les informations produites par MedRAG constituent une aide a l'orientation et ne remplacent pas l'avis d'un professionnel de sante.

L'application ne pose pas de diagnostic definitif et ne prescrit pas de traitement.
