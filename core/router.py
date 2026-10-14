# -*- coding: utf-8 -*-
"""Router central — distribue les requêtes API vers les apps enregistrées.

Chaque app expose `ROUTES` : liste de (method, prefix, handler).
Le handler reçoit (ctx, body) où ctx = {path, params} et retourne un dict JSON.
"""
import re


class Route:
    __slots__ = ("method", "pattern", "handler", "name")

    def __init__(self, method, pattern, handler, name=""):
        self.method = method.upper()
        self.pattern = re.compile("^" + pattern + "$")
        self.handler = handler
        self.name = name

    def match(self, method, path):
        if method != self.method:
            return None
        m = self.pattern.match(path)
        if not m:
            return None
        return m.groupdict()


_registry = []  # list[Route]


def register(routes):
    """routes : iterable de (method, pattern, handler[, name]).
    pattern : regex avec groupes nommés, ex: r'/api/sites/(?P<id>\\d+)'."""
    for r in routes:
        if len(r) == 4:
            _registry.append(Route(r[0], r[1], r[2], r[3]))
        else:
            _registry.append(Route(r[0], r[1], r[2]))


def routes():
    return list(_registry)


def handle(request):
    """Point d'entrée unique (compatible avec l'ancien backend.handle).
    request peut porter 'user'/'token' (injectés par le serveur) — ils sont
    fusionnés dans le ctx passé aux handlers."""
    path = request.get("path", "")
    method = request.get("method", "GET").upper()
    body = request.get("body", {}) or {}
    extra = {k: request[k] for k in ("user", "token") if k in request}
    for route in _registry:
        params = route.match(method, path)
        if params is not None:
            ctx = {"path": path, "params": params, **extra}
            try:
                return route.handler(ctx, body)
            except Exception as e:  # une app ne doit jamais tuer le serveur
                return {"ok": False, "error": f"{route.name or path}: {e}"}
    return {"ok": False, "error": f"route inconnue: {method} {path}"}
