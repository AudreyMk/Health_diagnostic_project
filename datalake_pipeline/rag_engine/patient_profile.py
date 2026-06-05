"""
Profil santé patient — table patient_profiles.
Stocke antécédents, traitements, allergies, mode de vie.
Séparé de auth.py : séparation auth / données médicales sensibles.

age et sex restent dans users (source de vérité unique).
"""
import json

import psycopg
from psycopg.rows import dict_row

from .config import PG_DSN


def _conn():
    return psycopg.connect(PG_DSN, row_factory=dict_row, autocommit=True)


def init_table():
    """Crée la table patient_profiles si elle n'existe pas (appelé au démarrage)."""
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS patient_profiles (
                user_id         TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                antecedents     JSONB NOT NULL DEFAULT '[]',
                chronic_disease BOOLEAN,
                treatments      JSONB NOT NULL DEFAULT '[]',
                allergies       JSONB NOT NULL DEFAULT '[]',
                lifestyle       JSONB NOT NULL DEFAULT '{}',
                created_at      TIMESTAMPTZ DEFAULT NOW(),
                updated_at      TIMESTAMPTZ DEFAULT NOW()
            )
        """)


def get_profile(user_id: str) -> dict | None:
    """
    Retourne le profil médical, ou None si absent (cas skip).
    Retourner None n'est pas une erreur — le chat fonctionne sans profil.
    """
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM patient_profiles WHERE user_id = %s", (user_id,)
        ).fetchone()
    if not row:
        return None
    d = dict(row)
    # Retire les métadonnées techniques non utiles au LLM
    d.pop("created_at", None)
    d.pop("updated_at", None)
    return d


def upsert_profile(user_id: str, data: dict):
    """
    Crée ou met à jour le profil médical du patient (UPSERT).
    Tous les champs sont optionnels — un body vide crée un profil vide.
    """
    with _conn() as conn:
        conn.execute("""
            INSERT INTO patient_profiles
                (user_id, antecedents, chronic_disease, treatments, allergies, lifestyle, updated_at)
            VALUES (%s, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s::jsonb, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                antecedents     = EXCLUDED.antecedents,
                chronic_disease = EXCLUDED.chronic_disease,
                treatments      = EXCLUDED.treatments,
                allergies       = EXCLUDED.allergies,
                lifestyle       = EXCLUDED.lifestyle,
                updated_at      = NOW()
        """, (
            user_id,
            json.dumps(data.get("antecedents") or []),
            data.get("chronic_disease"),        # None = "je ne sais pas"
            json.dumps(data.get("treatments") or []),
            json.dumps(data.get("allergies") or []),
            json.dumps(data.get("lifestyle") or {}),
        ))
