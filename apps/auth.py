# -*- coding: utf-8 -*-
"""App AUTH — inscription, connexion, déconnexion, profil.

Routes : /api/auth/register, /api/auth/login, /api/auth/logout,
/api/auth/me, /api/auth/setup-needed.
"""
from core import auth, db, router
from core.router import register


def setup_needed(ctx, body):
    """True si aucun utilisateur n'existe (premier lancement)."""
    return {"ok": True, "setup_needed": auth.user_count() == 0}


def register_user(ctx, body):
    email = body.get("email", "")
    password = body.get("password", "")
    display = body.get("display_name", "")
    # le premier utilisateur devient admin
    is_admin = auth.user_count() == 0
    ok, res = auth.create_user(email, password, display, is_admin=is_admin)
    if not ok:
        return {"ok": False, "error": res}
    # connexion automatique après inscription
    ok2, user = auth.verify_user(email, password)
    if not ok2:
        return {"ok": True, "user_id": res, "auto_login": False}
    token = auth.create_session(user["id"])
    return {"ok": True, "token": token, "user": user, "auto_login": True}


def login(ctx, body):
    ok, res = auth.verify_user(body.get("email", ""), body.get("password", ""))
    if not ok:
        return {"ok": False, "error": res}
    token = auth.create_session(res["id"])
    return {"ok": True, "token": token, "user": res}


def logout(ctx, body):
    # token transmis via body ou en-tête (le serveur le passe dans ctx)
    token = body.get("token") or ctx.get("token")
    if token:
        auth.destroy_session(token)
    return {"ok": True}


def me(ctx, body):
    user = ctx.get("user")
    if not user:
        return {"ok": False, "error": "non authentifié"}
    return {"ok": True, "user": user}


def change_password(ctx, body):
    user = ctx.get("user")
    if not user:
        return {"ok": False, "error": "non authentifié"}
    old = body.get("old_password", "")
    new = body.get("new_password", "")
    ok, res = auth.verify_user(user["email"], old)
    if not ok:
        return {"ok": False, "error": "ancien mot de passe incorrect"}
    if len(new) < 8:
        return {"ok": False, "error": "8 caractères minimum"}
    salt = __import__("secrets").token_bytes(16).hex()
    db.execute("UPDATE users SET pass_hash=?, salt=? WHERE id=?",
               (auth._hash_password(new, salt), salt, user["id"]))
    # invalide les autres sessions
    auth.destroy_user_sessions(user["id"])
    return {"ok": True}


ROUTES = [
    ("GET", r"/api/auth/setup-needed", setup_needed),
    ("POST", r"/api/auth/register", register_user),
    ("POST", r"/api/auth/login", login),
    ("POST", r"/api/auth/logout", logout),
    ("GET", r"/api/auth/me", me),
    ("POST", r"/api/auth/change-password", change_password),
]
register(ROUTES)
