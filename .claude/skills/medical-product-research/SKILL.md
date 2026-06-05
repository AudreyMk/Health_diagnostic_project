---

name: medical-product-research
description: Research and analyze digital health products, medical AI tools, symptom checkers, patient assistants, healthcare regulations, scientific literature and clinical guidelines. Use when working on MedRAG product strategy, competitors, differentiation, medical standards, patient journey, feature ideas, healthcare UX, or evidence-based improvements.
----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Medical Product Research

## Mission

This skill helps evolve MedRAG into an intelligent patient assistant, not just a medical chatbot.

MedRAG should be treated as:

> An AI-powered digital health product that helps patients describe symptoms, receive cautious prediagnostic hypotheses, follow symptom evolution, prepare medical consultations, and be oriented toward the most appropriate care pathway.

The goal is not only to search for information, but to transform research into concrete, useful, medically cautious and technically feasible product improvements.

## Core Priorities

Always prioritize MedRAG features in this order:

1. Prediagnostic reasoning
2. Symptom tracking
3. Consultation preparation
4. Patient history
5. Medical orientation
6. Doctor / pharmacy / healthcare facility recommendation

## Required Research Axes

When researching an idea, always consider these axes:

### 1. Competitive analysis

Compare MedRAG with existing tools when relevant:

* Ada Health
* Babylon
* Buoy Health
* Infermedica
* WebMD Symptom Checker
* Mayo Clinic Symptom Checker
* Doctolib
* K Health
* other relevant digital health tools

For each competitor, analyze:

* what the tool does;
* what user problem it solves;
* its strengths;
* its weaknesses;
* what MedRAG can learn from it;
* what MedRAG can do differently or better.

Do not simply list competitors. Always connect the analysis back to MedRAG.

### 2. Medical and scientific research

When useful, search for:

* scientific publications;
* clinical guidelines;
* HAS recommendations;
* WHO resources;
* NICE guidelines;
* public health recommendations;
* evidence-based symptom assessment methods.

Only integrate scientific or medical information if it is useful for the product, the report, the architecture, the UX or the safety of the tool.

Do not add medical complexity just to look advanced.

### 3. Regulation and safety

Always consider:

* RGPD / GDPR;
* HAS guidance;
* European MDR;
* AI Act;
* medical device risk;
* health data protection;
* user consent;
* transparency;
* explainability;
* non-substitution of medical advice.

MedRAG must remain medically cautious.

The tool may propose possible hypotheses, but must never present them as a confirmed diagnosis.

Preferred wording:

* “possible hypotheses”
* “medical possibilities to discuss with a professional”
* “recommended orientation”
* “warning signs”
* “consultation preparation”

Avoid:

* “confirmed diagnosis”
* “you have this disease”
* “you do not need to consult”
* “take this treatment”

### 4. Product differentiation

Always ask:

> Why would a patient use MedRAG instead of Ada, Babylon, Buoy or WebMD?

Strong differentiation opportunities include:

* intelligent patient report;
* symptom timeline;
* patient profile that evolves over time;
* preparation of medical consultation;
* contextualized orientation toward the right professional;
* healthcare map displayed only when orientation is needed;
* integration of patient history into future conversations;
* cautious RAG-based medical reasoning;
* specialist recommendation according to symptoms.

### 5. Academic value

For each idea, evaluate whether it is defendable in a Master project.

A good idea should be:

* useful for patients;
* medically cautious;
* technically feasible;
* explainable in a report;
* demonstrable during a defense;
* coherent with the current architecture.

Avoid ideas that are too broad, too commercial, too complex or impossible to demonstrate quickly.

## Research Method

When asked to research or analyze something, follow this structure:

### Step 1 — Clarify the product question

Identify the real question behind the request.

Examples:

* “How can MedRAG improve symptom tracking?”
* “How can MedRAG prepare a useful consultation report?”
* “How should MedRAG recommend a specialist?”
* “What can MedRAG learn from Ada Health?”

### Step 2 — Search and compare

Use current and reliable sources when research is required.

Prioritize:

* official medical organizations;
* regulatory bodies;
* academic publications;
* product documentation;
* reputable healthcare sources.

### Step 3 — Extract insights

Do not summarize blindly.

For each finding, explain:

* why it matters;
* what problem it solves;
* whether it applies to MedRAG;
* what risk it introduces;
* how it can be adapted.

### Step 4 — Transform into product recommendations

Every research task must produce actionable recommendations.

Use this format:

```markdown
## Recommendation

### Idea
[Name of the proposed improvement]

### Why it matters
[Patient value + medical/product value]

### How it works in MedRAG
[Concrete workflow]

### Required data
[Profile, symptoms, history, RAG results, location, etc.]

### UI impact
[Screen, component, user interaction]

### Backend impact
[API, database, RAG, logs, profile update]

### Medical safety
[Warnings, disclaimers, validation, limits]

### Complexity
Low / Medium / High

### Priority
P1 / P2 / P3

### Defense value
How this can be explained in the academic report or oral defense
```

## Output Rules

Never provide only a list of ideas.

Always include:

1. analysis;
2. product impact;
3. medical caution;
4. feasibility;
5. priority;
6. how it improves MedRAG.

If an idea is interesting but not feasible now, classify it as:

```text
Future evolution
```

If an idea is risky medically or legally, clearly say so and propose a safer alternative.

## MedRAG Current Context

MedRAG currently includes:

* React/Vite frontend;
* FastAPI backend;
* PostgreSQL with pgvector;
* MongoDB with geospatial search;
* Claude with tool use;
* RAG over pathologies, similar patients and clinical cases;
* FINESS healthcare facilities;
* authentication;
* conversation history;
* triage output;
* healthcare center recommendation.

The current technical base is solid.

The main weakness is not the RAG itself, but the lack of visible product value and patient-centered experience.

The priority is therefore to make MedRAG feel like a complete intelligent patient assistant.

## Key Product Direction

MedRAG V3 should focus on these demonstrable features:

1. Patient onboarding with initial health profile
2. Patient dashboard
3. Intelligent medical chat
4. Intelligent patient report
5. Intelligent orientation toward the right professional
6. Healthcare map
7. Symptom history

## Patient Profile Logic

At first registration, MedRAG should collect a basic patient health profile:

* age;
* sex;
* location or department;
* medical history;
* chronic diseases;
* current treatments;
* allergies;
* lifestyle;
* eating habits if useful.

This profile must be used to contextualize future conversations.

The profile must evolve over time.

If the user mentions a new allergy, new treatment, stopped treatment, chronic disease or relevant medical history, MedRAG should propose updating the profile.

Profile updates must not be automatic without explicit user confirmation.

For treatments, distinguish:

* chronic treatment;
* temporary treatment;
* active treatment;
* stopped treatment;
* unknown status;
* start date;
* end date;
* last confirmation date.

## Preferred Product Positioning

Use this positioning when reasoning about MedRAG:

> MedRAG is an AI-powered intelligent patient assistant that supports symptom tracking, cautious prediagnostic reasoning and orientation toward the most appropriate care pathway.

## Final Rule

Research is only useful if it helps MedRAG become more useful, safer, clearer, more innovative or easier to defend academically.
