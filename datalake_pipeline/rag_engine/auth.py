"""
Gestion des utilisateurs — inscription, connexion, validation de token.
Stockage dans PostgreSQL (tables users + sessions).
"""
import secrets
import uuid

import bcrypt
import psycopg
from psycopg.rows import dict_row

from .config import PG_DSN


def _conn():
    conn = psycopg.connect(PG_DSN, row_factory=dict_row, autocommit=True)
    return conn


def init_tables():
    """Crée les tables users et sessions si elles n'existent pas."""
    with _conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              TEXT PRIMARY KEY,
                name            TEXT NOT NULL,
                email           TEXT UNIQUE NOT NULL,
                password        TEXT NOT NULL,
                age             INTEGER,
                sex             CHAR(1),
                dept            TEXT,
                lat             REAL,
                lon             REAL,
                onboarding_done BOOLEAN DEFAULT FALSE,
                created_at      TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        # Migrations additives — idempotentes, sûres si la table existait déjà
        conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS dept TEXT")
        conn.execute(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_done BOOLEAN DEFAULT FALSE"
        )
        conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS lat REAL")
        conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS lon REAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT PRIMARY KEY,
                user_id    TEXT NOT NULL REFERENCES users(id),
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)


def register(name: str, email: str, password: str, age=None, sex=None):
    """Cree un compte. Retourne (user_id, None) ou (None, message_erreur)."""
    with _conn() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = %s", (email,)).fetchone():
            return None, "Cet email est deja utilise."
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        uid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO users (id, name, email, password, age, sex) VALUES (%s,%s,%s,%s,%s,%s)",
            (uid, name, email, hashed, age, sex),
        )
    return uid, None


def login(email: str, password: str):
    """Verifie les identifiants. Retourne (user_dict, None) ou (None, message_erreur)."""
    with _conn() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE email = %s", (email,)
        ).fetchone()
        if not user or not bcrypt.checkpw(password.encode(), user["password"].encode()):
            return None, "Email ou mot de passe incorrect."
        token = secrets.token_hex(32)
        conn.execute(
            "INSERT INTO sessions (token, user_id) VALUES (%s, %s)",
            (token, user["id"]),
        )
    return {
        "token":           token,
        "user_id":         user["id"],
        "name":            user["name"],
        "age":             user["age"],
        "sex":             user["sex"],
        "dept":            user.get("dept"),
        "lat":             user.get("lat"),
        "lon":             user.get("lon"),
        "onboarding_done": bool(user.get("onboarding_done", False)),
    }, None


def update_dept(user_id: str, dept: str):
    """Met à jour le département (rétrocompatibilité — utilisé par la géolocalisation)."""
    with _conn() as conn:
        conn.execute("UPDATE users SET dept = %s WHERE id = %s", (dept, user_id))


def update_user_profile(user_id: str, dept=None, age=None, sex=None, lat=None, lon=None):
    """Met à jour les champs de base du profil (dept, age, sex, lat, lon) — champs optionnels."""
    fields, values = [], []
    if dept is not None:
        fields.append("dept = %s"); values.append(dept)
    if age is not None:
        fields.append("age = %s");  values.append(age)
    if sex is not None:
        fields.append("sex = %s");  values.append(sex)
    if lat is not None:
        fields.append("lat = %s");  values.append(lat)
    if lon is not None:
        fields.append("lon = %s");  values.append(lon)
    if not fields:
        return
    values.append(user_id)
    with _conn() as conn:
        conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = %s", values)


def update_onboarding(user_id: str):
    """Marque l'onboarding comme terminé pour cet utilisateur."""
    with _conn() as conn:
        conn.execute(
            "UPDATE users SET onboarding_done = TRUE WHERE id = %s", (user_id,)
        )


def get_user(token: str) -> dict | None:
    """Retourne le profil utilisateur associe au token, ou None si invalide."""
    with _conn() as conn:
        row = conn.execute("""
            SELECT u.id AS user_id, u.name, u.age, u.sex, u.dept, u.lat, u.lon, u.onboarding_done
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = %s
        """, (token,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["onboarding_done"] = bool(d.get("onboarding_done", False))
    return d
