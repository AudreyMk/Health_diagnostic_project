"""
Stockage des conversations en PostgreSQL.
Tables : conversations + conversation_messages
"""
import json
import uuid
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

from .config import PG_DSN


def _conn():
    return psycopg.connect(PG_DSN, row_factory=dict_row, autocommit=True)


def init_tables():
    """Crée les tables si elles n'existent pas (appelé au démarrage de l'API)."""
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id         TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_messages (
                id              BIGSERIAL PRIMARY KEY,
                conversation_id TEXT NOT NULL REFERENCES conversations(id),
                role            TEXT NOT NULL,
                content         TEXT NOT NULL,
                created_at      TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        # Ajoute les colonnes de persistance si elles n'existent pas encore
        conn.execute(
            "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS report_json JSONB"
        )
        conn.execute(
            "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS triage_json JSONB"
        )


def create(user_id: str) -> str:
    """Crée une nouvelle conversation vide. Retourne l'id."""
    conv_id = str(uuid.uuid4())
    with _conn() as conn:
        conn.execute(
            "INSERT INTO conversations (id, user_id) VALUES (%s, %s)",
            (conv_id, user_id),
        )
    return conv_id


def get_messages(conv_id: str) -> list[dict]:
    """Retourne l'historique (role + content) d'une conversation."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT role, content FROM conversation_messages "
            "WHERE conversation_id = %s ORDER BY created_at",
            (conv_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def save_messages(conv_id: str, new_msgs: list[dict]):
    """Ajoute des messages à la conversation."""
    with _conn() as conn:
        for msg in new_msgs:
            conn.execute(
                "INSERT INTO conversation_messages (conversation_id, role, content) "
                "VALUES (%s, %s, %s)",
                (conv_id, msg["role"], msg["content"]),
            )


def belongs_to_user(conv_id: str, user_id: str) -> bool:
    """Vérifie que la conversation appartient bien à cet utilisateur."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM conversations WHERE id = %s AND user_id = %s",
            (conv_id, user_id),
        ).fetchone()
    return row is not None


def save_report(conv_id: str, report: dict):
    """Persiste la fiche pré-consultation dans la conversation."""
    with _conn() as conn:
        conn.execute(
            "UPDATE conversations SET report_json = %s::jsonb WHERE id = %s",
            (json.dumps(report), conv_id),
        )


def get_report(conv_id: str) -> dict | None:
    """Retourne la fiche pré-consultation d'une conversation, ou None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT report_json FROM conversations WHERE id = %s",
            (conv_id,),
        ).fetchone()
    # psycopg3 désérialise automatiquement JSONB en dict
    return row["report_json"] if row and row["report_json"] else None


def save_triage(conv_id: str, triage: dict):
    """Persiste le triage (orientation + hypothèses) dans la conversation."""
    with _conn() as conn:
        conn.execute(
            "UPDATE conversations SET triage_json = %s::jsonb WHERE id = %s",
            (json.dumps(triage), conv_id),
        )


def get_triage(conv_id: str) -> dict | None:
    """Retourne le triage persisté d'une conversation, ou None."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT triage_json FROM conversations WHERE id = %s",
            (conv_id,),
        ).fetchone()
    return row["triage_json"] if row and row["triage_json"] else None


def list_for_user(user_id: str) -> list[dict]:
    """Liste les 20 dernières conversations avec métadonnées de triage pour le dashboard."""
    with _conn() as conn:
        rows = conn.execute("""
            SELECT c.id, c.created_at,
                (SELECT content FROM conversation_messages
                 WHERE conversation_id = c.id
                 ORDER BY created_at DESC LIMIT 1) AS last_message,
                c.triage_json->>'color'       AS triage_color,
                c.triage_json->>'orientation' AS triage_orientation,
                (c.report_json IS NOT NULL)   AS has_report
            FROM conversations c
            WHERE c.user_id = %s
            ORDER BY c.created_at DESC
            LIMIT 20
        """, (user_id,)).fetchall()
    return [{
        "id":                  r["id"],
        "created_at":          r["created_at"].isoformat(),
        "last_message":        (r["last_message"] or "Nouvelle conversation")[:60],
        "triage_color":        r["triage_color"],
        "triage_orientation":  r["triage_orientation"],
        "has_report":          bool(r["has_report"]),
    } for r in rows]
