# -*- coding: utf-8 -*-
"""App CONTENT — création d'articles SEO par IA (OpenRouter free + BeatAPI).

Sprint 1 : génération, brouillon, publication WordPress.
Routes enregistrées sur /api/content/*.
"""
import re

from core import db
from core.router import register
from providers import beatapi, openrouter
from . import wordpress


def slugify(text):
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_-]+", "-", s)[:60]


# ---------- Handlers ----------

def status(ctx, body):
    keys = openrouter.get_api_key()
    free = openrouter.list_free_models()
    return {
        "ok": True,
        "openrouter_configured": bool(keys),
        "openrouter_free_models_count": len(free),
        "beatapi_configured": beatapi.configured(),
    }


def generate(ctx, body):
    """POST /api/content/generate — génère un article (sans publier).
    body : site_id, topic, keywords, length, custom_instructions, research(bool)"""
    site = db.fetchone("SELECT * FROM sites WHERE id=?", (body.get("site_id"),))
    if not site:
        return {"ok": False, "error": "site introuvable"}

    # recherche de sources fraîches (mode dégradé si pas de clé BeatAPI)
    research_block = ""
    if body.get("research"):
        research_block = beatapi.research_context(
            body.get("topic", ""), body.get("keywords", ""))

    try:
        art = openrouter.generate_article_json(
            topic=body.get("topic", ""),
            keywords=body.get("keywords", ""),
            site_name=site["name"],
            site_url=site["url"],
            length=body.get("length", "standard"),
            custom_instructions=body.get("custom_instructions", ""),
        )
    except Exception as e:
        return {"ok": False, "error": str(e)}

    if research_block:
        # on injecte les sources dans le contenu avant la conclusion si pertinent
        art["content"] = art["content"] + "\n\n## Sources\n" + research_block
        art["internal_links"] = art.get("internal_links", [])

    return {
        "ok": True,
        "article": art,
        "model": art.get("_model"),
        "research_used": bool(research_block),
    }


def save_draft(ctx, body):
    """POST /api/content/draft — génère et enregistre en brouillon local."""
    site = db.fetchone("SELECT * FROM sites WHERE id=?", (body.get("site_id"),))
    if not site:
        return {"ok": False, "error": "site introuvable"}
    gen = generate(ctx, body)
    if not gen.get("ok"):
        return gen
    art = gen["article"]
    cur = db.execute(
        """INSERT INTO articles
           (site_id, title, slug, content, meta_description, status, seo_title, provider, model)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (site["id"], art["title"], slugify(art.get("slug") or art["title"]),
         art["content"], art.get("meta_description", "")[:300], "draft",
         art.get("seo_title"), "openrouter", gen.get("model")),
    )
    return {"ok": True, "article_id": cur.lastrowid, "article": art, "model": gen.get("model")}


def publish(ctx, body):
    """POST /api/content/publish — génère et publie sur WordPress (ou brouillon WP)."""
    site = db.fetchone("SELECT * FROM sites WHERE id=?", (body.get("site_id"),))
    if not site:
        return {"ok": False, "error": "site introuvable"}
    if not site.get("wp_user"):
        return {"ok": False, "error": "identifiants WordPress manquants pour ce site"}

    gen = generate(ctx, body)
    if not gen.get("ok"):
        return gen
    art = gen["article"]
    wp_status = "publish" if body.get("publish_now") else "draft"
    ok, wp, code = wordpress.publish_post(
        site, art["title"], slugify(art.get("slug") or art["title"]),
        art["content"], art.get("seo_title", ""), art.get("meta_description", ""),
        status=wp_status,
    )
    if not ok:
        return {"ok": False, "error": f"WordPress HTTP {code}: {str(wp)[:200]}"}

    db.execute(
        """INSERT INTO articles
           (site_id, wp_post_id, title, slug, content, meta_description, status,
            seo_title, provider, model, published_at)
           VALUES (?,?,?,?,?,?,?,?,?,?, datetime('now'))""",
        (site["id"], wp["id"], art["title"], slugify(art.get("slug") or art["title"]),
         art["content"], art.get("meta_description", "")[:300], wp_status,
         art.get("seo_title"), "openrouter", gen.get("model")),
    )
    return {
        "ok": True,
        "wp_id": wp["id"],
        "wp_link": wp.get("link"),
        "wp_status": wp_status,
        "model": gen.get("model"),
    }


def free_models(ctx, body):
    return {"ok": True, "models": openrouter.list_free_models()}


ROUTES = [
    ("GET", r"/api/content/status", status),
    ("POST", r"/api/content/generate", generate),
    ("POST", r"/api/content/draft", save_draft),
    ("POST", r"/api/content/publish", publish),
    ("GET", r"/api/content/models", free_models),
]
register(ROUTES)
