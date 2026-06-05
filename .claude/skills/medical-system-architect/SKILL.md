---
name: medical-system-architect
description: Validate and design MedRAG technical architecture. Use when adding features, changing database schema, modifying FastAPI endpoints, updating React components, changing RAG behavior, storing patient data, adding reports, symptom history, patient profile, healthcare recommendations or reviewing technical coherence.
---

# Medical System Architect

## Mission

Protect MedRAG architecture.

This skill ensures that every new feature integrates cleanly with the existing system:

- React frontend
- FastAPI backend
- PostgreSQL
- pgvector
- MongoDB
- Claude tool use
- RAG engine
- conversation history
- authentication

Do not design features from a product perspective only.  
Focus on architecture, maintainability, data flow, security and technical coherence.

## Current MedRAG Architecture

Frontend:

- `frontend/src/App.jsx`
- `frontend/src/LoginPage.jsx`
- `frontend/src/ResultsPanel.jsx`
- `frontend/src/ConsultationCard.jsx`
- `frontend/src/index.css`

Backend:

- `datalake_pipeline/rag_engine/api.py`
- `datalake_pipeline/rag_engine/auth.py`
- `datalake_pipeline/rag_engine/conversation.py`
- `datalake_pipeline/rag_engine/llm_client.py`
- `datalake_pipeline/rag_engine/retriever.py`
- `datalake_pipeline/rag_engine/config.py`

PostgreSQL tables:

- `users`
- `sessions`
- `conversations`
- `conversation_messages`
- `query_logs`
- `pathology_documents`
- `patient_descriptions`
- `clinical_cases`

MongoDB:

- mainly FINESS / healthcare centers
- geospatial healthcare facility search

RAG sources:

- pathology documents
- similar patients
- clinical cases
- healthcare centers

## Core Rule

Before implementing any feature, first answer:

1. Which existing files are impacted?
2. Which existing tables are impacted?
3. Is a new table really necessary?
4. Is MongoDB or PostgreSQL more appropriate?
5. Does this affect the RAG pipeline?
6. Does this affect patient privacy?
7. Does this affect conversation history?
8. Does this affect frontend state?
9. Can existing modules be reused?
10. What is the simplest safe implementation?

## Architecture Principles

Prefer extending existing modules before creating new ones.

Avoid unnecessary files.

Avoid duplicating logic.

Avoid creating services unless they are clearly justified.

Keep the architecture understandable for a Master project.

Do not over-engineer.

## Database Rules

Use PostgreSQL for:

- users
- sessions
- conversations
- conversation messages
- patient profile
- consultation reports
- symptom history
- audit logs
- structured relational data

Use pgvector only for semantic search data.

Use MongoDB for:

- FINESS healthcare centers
- geospatial queries
- healthcare facility metadata

Do not store patient medical profile in MongoDB unless there is a strong reason.

## Patient Data Rules

Patient data is sensitive.

For patient profile features, prefer a PostgreSQL table such as:

- `patient_profiles`

For symptom tracking, consider:

- `symptom_events`
- or structured JSON fields if the first version must stay simple

For generated consultation reports, consider:

- `consultation_reports`

Never store important patient health data only in frontend localStorage.

Frontend localStorage may store tokens and minimal UI state only.

## Conversation Rules

Existing conversation storage is in:

- `conversations`
- `conversation_messages`

Use `conversation.py` for conversation persistence.

Do not bypass conversation storage.

If a feature depends on a conversation, link it to `conversation_id`.

Examples:

- consultation report should link to `conversation_id`
- symptom summary should link to `conversation_id`
- triage result should link to `conversation_id`

## RAG Rules

Do not modify the RAG pipeline unless necessary.

Before changing retrieval, explain:

- why current retrieval is insufficient;
- which pool is affected;
- expected improvement;
- risk of regression.

Current RAG pools:

- pathologies
- similar patients
- clinical cases
- healthcare centers

Prefer adding a lightweight post-processing step before redesigning retrieval.

## LLM Rules

Claude output must remain medically cautious.

Do not add confidence percentages to medical hypotheses.

Use:

- possible hypotheses
- paths to discuss with a professional
- orientation recommendation
- warning signs

Avoid:

- confirmed diagnosis
- probability scores
- treatment prescriptions

If adding new structured outputs, use explicit tags such as:

- `<TRIAGE>`
- `<REPORT>`
- `<PROFILE_UPDATE>`

Always define parsing failure behavior.

The application must still work if Claude output parsing fails.

## API Rules

Before adding a new endpoint, check whether an existing endpoint can be extended safely.

Current API areas:

- auth
- conversations
- chat
- centers
- health

Use clear endpoint names.

Examples:

- `GET /auth/me`
- `PUT /auth/profile`
- `POST /conversations`
- `GET /conversations`
- `GET /conversations/{id}/messages`
- `POST /conversations/{id}/chat`

For new patient profile features, possible endpoints:

- `GET /patient/profile`
- `PUT /patient/profile`

For reports:

- `GET /conversations/{id}/report`
- `POST /conversations/{id}/report`

## Frontend Rules

Reuse existing layout before creating new flows.

Current key components:

- `App.jsx`
- `LoginPage.jsx`
- `ResultsPanel.jsx`
- `ConsultationCard.jsx`

Add new components only when they represent a distinct UI concept.

Good examples:

- `PatientProfileForm.jsx`
- `PatientDashboard.jsx`
- `SymptomTimeline.jsx`
- `ConsultationReport.jsx`

Avoid creating too many small components prematurely.

## Feature Architecture Template

For every feature, output:

## Architecture Decision

Short decision summary.

## Impacted Files

List exact files.

## Database Impact

Tables to reuse, modify or create.

## API Impact

Endpoints to reuse, modify or create.

## Frontend Impact

Components and state changes.

## RAG Impact

None / minor / major.

## LLM Impact

Prompt, parsing, structured output.

## Security and Privacy

Patient data risks and safeguards.

## Implementation Plan

Step-by-step plan.

## Risk

Technical, medical or UX risks.

## Recommendation

Implement now / postpone / redesign.

## Stop Conditions

Stop implementation and ask the user if:

- database schema must change significantly;
- authentication behavior changes;
- patient medical data storage changes;
- RAG retrieval logic changes;
- LLM structured output format changes;
- feature requires deleting or rewriting existing modules.

## Final Rule

MedRAG should evolve by extending its current architecture, not by constantly reinventing it.