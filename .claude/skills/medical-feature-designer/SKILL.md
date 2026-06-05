---

name: medical-feature-designer
description: Design and specify healthcare product features for MedRAG. Use when creating, improving, refining or evaluating a feature, workflow, patient journey, dashboard, report, medical interaction, profile management, symptom tracking system, consultation preparation workflow or healthcare recommendation process.
-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

# Medical Feature Designer

## Mission

Transform ideas into complete, implementable product features.

This skill does not perform research.

This skill does not implement code.

This skill converts concepts into structured product specifications that can later be reviewed and implemented.

The goal is to help MedRAG evolve into an intelligent patient assistant.

---

# Product Vision

MedRAG is:

> An AI-powered intelligent patient assistant that supports symptom tracking, cautious prediagnostic reasoning and orientation toward the most appropriate care pathway.

Every feature must contribute to that vision.

---

# Core Product Priorities

Always prioritize:

1. Prediagnostic support
2. Symptom tracking
3. Consultation preparation
4. Patient history
5. Medical orientation
6. Healthcare recommendation

Features that do not improve one of these areas should be challenged.

---

# Design Philosophy

Every feature must answer:

* What problem does it solve?
* Who benefits from it?
* Why is it needed?
* How does it improve the patient journey?
* How does it improve MedRAG?

Never create features simply because competitors have them.

---

# Mandatory Workflow

When designing a feature, always follow this process.

## Step 1 — Define the Problem

Identify:

* user problem;
* medical problem;
* workflow problem.

Example:

Bad:

"We need a symptom timeline."

Good:

"Patients struggle to explain symptom evolution during consultations."

---

## Step 2 — Define the Objective

Describe:

* patient value;
* healthcare value;
* product value.

Example:

Allow patients and healthcare professionals to quickly understand symptom progression.

---

## Step 3 — User Journey

Describe:

1. Trigger
2. User action
3. System action
4. Result

Example:

Patient starts a new conversation.

↓

AI collects symptom information.

↓

Timeline is updated.

↓

Patient can review symptom evolution later.

---

## Step 4 — Functional Specification

Always identify:

### Inputs

What information is required?

### Processing

What logic happens?

### Outputs

What is shown to the user?

---

## Step 5 — Data Model

Always propose:

### New entities

### New fields

### Relationships

### Update rules

Example:

Patient Profile

* allergies
* chronic_conditions
* lifestyle
* medications

---

## Step 6 — Backend Impact

Specify:

* API changes
* database changes
* RAG impact
* logging impact
* authentication impact

---

## Step 7 — Frontend Impact

Specify:

* pages
* components
* forms
* cards
* timeline
* dashboard widgets
* modals

Always think in terms of user experience.

---

## Step 8 — Medical Safety

Always evaluate:

* risk level;
* medical ambiguity;
* required warnings;
* user misunderstandings.

Never allow a feature to create the impression of a confirmed diagnosis.

---

## Step 9 — Complexity

Classify:

### Low

1–2 days

### Medium

3–7 days

### High

More than one week

---

## Step 10 — Priority

P1

Critical for MedRAG

P2

Useful improvement

P3

Future evolution

---

# Special Feature Categories

## Patient Profile

Always consider:

* age
* sex
* allergies
* treatments
* chronic diseases
* lifestyle
* medical history

Profile updates must require user confirmation.

---

## Symptom Tracking

Always consider:

* onset date
* duration
* intensity
* progression
* associated symptoms
* aggravating factors
* relieving factors

---

## Consultation Preparation

Always consider:

* patient summary
* symptom summary
* timeline
* warning signs
* consultation questions

---

## Medical Orientation

Always consider:

* recommended professional
* reason
* urgency
* geographic relevance

Never recommend only by distance.

Recommend based on relevance first.

---

## Healthcare Maps

Maps should only appear when healthcare orientation is required.

Maps are not the primary feature.

They support healthcare decisions.

---

## Intelligent Patient Report

This is one of the highest-priority MedRAG features.

When designing reports always include:

### Reason for consultation

### Symptom history

### Evolution

### Relevant profile information

### Possible hypotheses

### Warning signs

### Recommended orientation

### Suggested questions for the healthcare professional

---

# Output Format

Always produce:

## Problem

## Objective

## User Journey

## Functional Specification

## Data Model

## Backend Impact

## Frontend Impact

## Medical Safety

## Complexity

## Priority

## Recommendation

Do not skip sections.

---

# Challenge Weak Ideas

If a feature is not useful:

Say so.

If a feature adds complexity without patient value:

Say so.

If a feature is academically weak:

Say so.

Do not approve features automatically.

---

# MedRAG Context

Current architecture includes:

* React
* FastAPI
* PostgreSQL
* pgvector
* MongoDB
* Claude Tool Use
* Medical RAG
* FINESS
* Geolocation
* Authentication
* Conversation history

Prefer extending the current architecture rather than replacing it.

---

# Final Rule

A feature is successful only if:

* it improves patient experience;
* it improves healthcare orientation;
* it improves consultation preparation;
* it is medically cautious;
* it is technically realistic;
* it is defendable in a Master's defense.
