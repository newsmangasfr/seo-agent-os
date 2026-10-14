# -*- coding: utf-8 -*-
"""Auth — utilisateurs, sessions, PBKDF2, cookies HttpOnly.

Stdlib uniquement. Stockage SQLite (table users + sessions).
"""
import hashlib
import hmac
import os
import secrets
import sqlite3
import time

from core import db

SESSION_COOKIE = "aos_session"
SESSION_TTL = 60 * 60 * 24 * 7   # 7 jours
PBKDF2_ROUNDS = 120_000


# ---------- schéma ----------

def init_auth():
    with db.db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            pass_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            display_name TEXT,
            is_admin INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            last_login TEXT
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at REAL,
            expires_at REAL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
        """)


# ---------- mots de passe ----------

def _hash_password(password, salt):
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ROUNDS)
    return dk.hex()


def create_user(email, password, display_name=None, is_admin=False):
    """Crée un utilisateur. Retourne (ok, user_id|erreur)."""
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return False, "email invalide"
    if not password or len(password) < 8:
        return False, "mot de passe : 8 caractères minimum"
    if db.fetchone("SELECT id FROM users WHERE email=?", (email,)):
        return False, "cet email existe déjà"
    salt = secrets.token_bytes(16).hex()
    pass_hash = _hash_password(password, salt)
    cur = db.execute(
        "INSERT INTO users (email, pass_hash, salt, display_name, is_admin) VALUES (?,?,?,?,?)",
        (email, pass_hash, salt, display_name or email.split("@")[0], 1 if is_admin else 0))
    return True, cur.lastrowid


def verify_user(email, password):
    """Vérifie les identifiants. Retourne (ok, user_dict|erreur)."""
    email = (email or "").strip().lower()
    user = db.fetchone("SELECT * FROM users WHERE email=?", (email,))
    if not user:
        # temps constant même si l'utilisateur n'existe pas (anti-timing)
        _hash_password(password or "", "00" * 16)
        return False, "email ou mot de passe incorrect"
    if not hmac.compare_digest(_hash_password(password or "", user["salt"]), user["pass_hash"]):
        return False, "email ou mot de passe incorrect"
    db.execute("UPDATE users SET last_login=datetime('now') WHERE id=?", (user["id"],))
    user.pop("pass_hash", None)
    user.pop("salt", None)
    return True, user


# ---------- sessions ----------

def create_session(user_id, ttl=SESSION_TTL):
    token = secrets.token_urlsafe(32)
    now = time.time()
    db.execute(
        "INSERT INTO sessions (token, user_id, created_at, expires_at) VALUES (?,?,?,?)",
        (token, user_id, now, now + ttl))
    # purge des sessions expirées (par lots, pas à chaque appel massif)
    db.execute("DELETE FROM sessions WHERE expires_at < ?", (now,))
    return token


def get_session_user(token):
    """Retourne le user de la session ou None (expirée/supprimée)."""
    if not token:
        return None
    row = db.fetchone("SELECT * FROM sessions WHERE token=?", (token,))
    if not row:
        return None
    if row["expires_at"] < time.time():
        db.execute("DELETE FROM sessions WHERE token=?", (token,))
        return None
    return db.fetchone("SELECT * FROM users WHERE id=?", (row["user_id"],))


def destroy_session(token):
    if token:
        db.execute("DELETE FROM sessions WHERE token=?", (token,))


def destroy_user_sessions(user_id):
    db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))


def user_count():
    return db.fetchone("SELECT COUNT(*) c FROM users")["c"]


# ---------- cookies ----------

def session_cookie_header(token):
    """Cookie HttpOnly, SameSite=Lax, Secure quand HTTPS."""
    parts = [
        f"{SESSION_COOKIE}={token}",
        "Path=/",
        "HttpOnly",
        "SameSite=Lax",
        f"Max-Age={SESSION_TTL}",
    ]
    # Secure uniquement si le site est servi en HTTPS (xCloud staging est https)
    if os.environ.get("AOS_FORCE_HTTPS", "1") == "1":
        parts.append("Secure")
    return "; ".join(parts)


def clear_cookie_header():
    return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"


def token_from_headers(headers):
    """Extrait le token de session depuis les en-têtes Cookie."""
    cookie = headers.get("Cookie", "") or headers.get("cookie", "")
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith(SESSION_COOKIE + "="):
            return part[len(SESSION_COOKIE) + 1:]
    return None


# ---------- utilisateur depuis une requête ----------

def user_from_headers(headers):
    """Retourne le user connecté ou None. Nettoie l'objet (pas de secrets)."""
    token = token_from_headers(headers)
    if not token:
        return None
    user = get_session_user(token)
    if user:
        user.pop("pass_hash", None)
        user.pop("salt", None)
    return user
