# -*- coding: utf-8 -*-
"""App TOOLS — options intelligentes du Studio (issues de l'analyse MCP).

- Recherche de mots-clés Google (gratuit)
- Liens internes depuis le sitemap WordPress (gratuit)
- Transcription audio -> article (Groq Whisper)
Routes : /api/tools/keywords, /api/tools/internal-links, /api/tools/transcribe
"""
import base64
import re

from core import db
from core.router import register
from providers import groq, keywords, openrouter, sitemap


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


def groq_status(ctx, body):
    return {"ok": True, "configured": groq.configured()}


def transcribe_audio(ctx, body):
    """POST /api/tools/transcribe — transcrit un audio puis rédige un article.
    body : site_id, audio_base64, filename, topic, keywords, length,
           write_article (bool), language
    Retourne la transcription, et si write_article : l'article généré."""
    if not groq.configured():
        return {"ok": False, "error": "clé Groq absente (configure-la dans les clés API)"}
    audio_b64 = body.get("audio_base64", "")
    if not audio_b64:
        return {"ok": False, "error": "audio requis (base64)"}
    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception:
        return {"ok": False, "error": "audio base64 invalide"}

    filename = body.get("filename", "audio.mp3")
    ok, text = groq.transcribe(audio_bytes, filename, body.get("language", "fr"))
    if not ok:
        return {"ok": False, "error": text}
    result = {"ok": True, "transcription": text, "words": len(text.split())}

    # option : rédiger un article depuis la transcription
    if body.get("write_article"):
        site = db.fetchone("SELECT * FROM sites WHERE id=?", (body.get("site_id"),))
        topic = body.get("topic") or text[:120]
        instructions = (
            "Rédige un article SEO complet en français à partir de cette "
            "transcription. Reformule naturellement (ne copie pas mot à mot), "
            "structure en H1/H2/H3, et assure-toi que ce soit publiable tel quel.\n\n"
            f"TRANSCRIPTION SOURCE :\n{text[:12000]}")
        try:
            art = openrouter.generate_article_json(
                topic=topic,
                keywords=body.get("keywords", ""),
                site_name=site["name"] if site else "Agent OS",
                site_url=site["url"] if site else None,
                length=body.get("length", "standard"),
                custom_instructions=instructions,
            )
            result["article"] = art
            result["model"] = art.get("_model")
        except Exception as e:
            result["article_error"] = str(e)
    return result


ROUTES = [
    ("POST", r"/api/tools/keywords", keyword_research),
    ("POST", r"/api/tools/internal-links", internal_links),
    ("POST", r"/api/tools/transcribe", transcribe_audio),
    ("GET", r"/api/tools/groq-status", groq_status),
]
register(ROUTES)
