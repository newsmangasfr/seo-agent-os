#!/usr/bin/env python
"""Serveur HTTP pour SEO Agent OS - sert le dashboard et l'API backend."""
import json
import os
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend import handle  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        pass  # logs silencieux

    def do_GET(self):
        # Protection par mot de passe (désactivée si variable DASH_PASSWORD vide)
        expected = os.environ.get("DASH_PASSWORD", "")
        if expected and not self.path.startswith("/auth"):
            cookie = self.headers.get("Cookie", "")
            if "saos_auth=1" not in cookie:
                self.send_response(302)
                self.send_header("Location", "/auth.html")
                self.end_headers()
                return
        if self.path.startswith("/api/"):
            result = handle({"path": self.path, "method": "GET", "body": {}})
            self._json(result)
        else:
            super().do_GET()

    def do_POST(self):
        # vérifier l'auth sur toutes les routes /api/ mutatrices (sauf /auth)
        expected = os.environ.get("DASH_PASSWORD", "")
        if expected and self.path != "/auth":
            cookie = self.headers.get("Cookie", "")
            if "saos_auth=1" not in cookie:
                self._json({"ok": False, "error": "non authentifié"})
                return
        if self.path == "/auth":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            if body == f"password={expected}":
                self.send_response(302)
                self.send_header("Set-Cookie", "saos_auth=1; HttpOnly; Path=/; Max-Age=604800")
                self.send_header("Location", "/dashboard.html")
                self.end_headers()
            else:
                self._json({"ok": False, "error": "mot de passe incorrect"})
            return
        if self.path.startswith("/api/"):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length).decode() if length else "{}"
            try:
                body = json.loads(raw) if raw else {}
            except Exception:
                body = {}
            result = handle({"path": self.path, "method": "POST", "body": body})
            self._json(result)
        else:
            self.send_error(404)

    def do_DELETE(self):
        if self.path.startswith("/api/"):
            result = handle({"path": self.path, "method": "DELETE", "body": {}})
            self._json(result)
        else:
            self.send_error(404)

    def _json(self, data):
        payload = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8000))
    print(f"SEO Agent OS : http://localhost:{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
