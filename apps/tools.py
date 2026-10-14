# -*- coding: utf-8 -*-
"""App TOOLS — options intelligentes du Studio (issues de l'analyse MCP).

- Recherche de mots-clés Google (gratuit)
- Liens internes depuis le sitemap WordPress (gratuit)
Routes : /api/tools/keywords, /api/tools/internal-links
"""
from core import db
from core.router import register
from providers import keywords, sitemap


def keyword_research(ctx, body):
    """POST /api/tools/keywords — recherche de mots-clés pour un sujet.
    body : topic, keywords (optionnel), lang"""
    topic = body.get("topic", "").strip()
    if not topic:
        return {"ok": False, "error": "sujet requis"}
    ok, data = keywords.research(topic, body.get("keywords", ""), body.get("lang", "fr"))
    return {"ok": ok, "data": data} if ok else {"ok": False, "error": "recherche échouée"}


def internal_links(ctx, body):
    """POST /api/tools/internal-links — liens internes depuis le sitemap.
    body : site_id, topic, keywords"""
    site = db.fetchone("SELECT * FROM sites WHERE id=?", (body.get("site_id"),))
    if not site:
        return {"ok": False, "error": "site introuvable"}
    ok, links = sitemap.suggest_internal_links(
        site["url"], body.get("topic", ""), body.get("keywords", ""))
    return {"ok": True, "links": links, "site": site["url"]} if ok else \
           {"ok": True, "links": [], "note": "sitemap inaccessible"}


ROUTES = [
    ("POST", r"/api/tools/keywords", keyword_research),
    ("POST", r"/api/tools/internal-links", internal_links),
]
register(ROUTES)
