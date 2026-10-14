#!/usr/bin/env python
"""Serveur HTTP Agent OS — sert le dashboard, la landing et l'API.

Protection : toute page /route API nécessite une session valide,
sauf la landing (/), les assets statiques et les routes d'auth.
"""
import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import auth
from backend import handle  # noqa: E402  (enregistre toutes les routes + init db)

ROOT = os.path.dirname(os.path.abspath(__file__))

# chemins publics (pas de session requise)
PUBLIC_PATHS = {"/", "/index.html", "/auth.html", "/flow3d.js",
                "/theme-scene.css", "/theme-3d.css", "/app.js", "/styles.css",
                "/auth.js", "/landing.js"}
PUBLIC_PREFIXES = ("/assets/", "/api/auth/", "/fonts")


def _is_public(path):
    if path in PUBLIC_PATHS:
        return True
    return any(path.startswith(p) for p in PUBLIC_PREFIXES)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        pass  # logs silencieux

    # ---------- helpers ----------
    def _current_user(self):
        return auth.user_from_headers(self.headers)

    def _set_cookie(self, value):
        self.send_header("Set-Cookie", value)

    def _json(self, data, extra_headers=None):
        payload = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        for k, v in (extra_headers or {}):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def _redirect(self, location, cookie=None):
        self.send_response(302)
        self.send_header("Location", location)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def _forbidden(self, msg="non authentifié"):
        self._json({"ok": False, "error": msg})

    # ---------- GET ----------
    def do_GET(self):
        full = self.path
        path = full.split("?")[0]
        if not _is_public(path):
            if not self._current_user():
                # page HTML -> login ; API -> 401 JSON
                if path.startswith("/api/"):
                    self._forbidden()
                else:
                    self._redirect("/auth.html")
                return
        if path.startswith("/api/"):
            user = self._current_user()
            ctx = {"path": full, "method": "GET", "body": {},
                   "user": user, "token": auth.token_from_headers(self.headers)}
            self._json(handle(ctx))
        else:
            super().do_GET()

    # ---------- POST ----------
    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length).decode() if length else "{}"
        try:
            body = json.loads(raw) if raw else {}
        except Exception:
            body = {}

        # routes d'auth : publiques, mais peuvent poser un cookie
        if path.startswith("/api/auth/"):
            user = self._current_user()
            ctx = {"path": path, "method": "POST", "body": body,
                   "user": user, "token": auth.token_from_headers(self.headers)}
            result = handle(ctx)
            headers = []
            if result.get("ok") and result.get("token"):
                headers.append(("Set-Cookie", auth.session_cookie_header(result["token"])))
                result.pop("token", None)  # le token reste dans le cookie
            elif path.endswith("/logout"):
                headers.append(("Set-Cookie", auth.clear_cookie_header()))
            self._json(result, extra_headers=headers)
            return

        if not _is_public(path) and not self._current_user():
            self._forbidden()
            return

        if path.startswith("/api/"):
            user = self._current_user()
            ctx = {"path": path, "method": "POST", "body": body,
                   "user": user, "token": auth.token_from_headers(self.headers)}
            self._json(handle(ctx))
        else:
            self.send_error(404)

    # ---------- DELETE ----------
    def do_DELETE(self):
        path = self.path.split("?")[0]
        if not _is_public(path) and not self._current_user():
            self._forbidden()
            return
        if path.startswith("/api/"):
            user = self._current_user()
            ctx = {"path": path, "method": "DELETE", "body": {},
                   "user": user, "token": auth.token_from_headers(self.headers)}
            self._json(handle(ctx))
        else:
            self.send_error(404)


if __name__ == "__main__":
    auth.init_auth()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8000))
    print(f"Agent OS : http://localhost:{port}")
    if auth.user_count() == 0:
        print("  -> Aucun utilisateur : ouvre /auth.html pour créer le premier compte (admin).")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
