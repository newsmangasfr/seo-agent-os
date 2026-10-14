# -*- coding: utf-8 -*-
"""BeatAPI — recherche web / social pour alimenter les articles en données fraîches.

BeatAPI est facturé par appel ; ici on l'utilise ponctuellement (recherche de
sources avant rédaction). Clé dans api_keys.json ('beatapi') ou $BEATAPI_KEY.
Si pas de clé ou d'échec, les apps doivent continuer sans (mode dégradé).
"""
import os

import json

from core import http

KEYS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api_keys.json")


def get_api_key():
    if os.environ.get("BEATAPI_KEY"):
        return os.environ["BEATAPI_KEY"]
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE) as f:
                return json.load(f).get("beatapi")
        except Exception:
            return None
    return None


def configured():
    return bool(get_api_key())


def web_search(query, limit=5):
    """Recherche web via BeatAPI. Retourne (ok, results, error).
    results : [{title, url, description, date}]"""
    key = get_api_key()
    if not key:
        return False, [], "clé BeatAPI absente"
    status, resp = http.post_json(
        "https://api.beatapi.com/v1/web/search",
        data={"query": query, "limit": limit},
        headers={"Authorization": f"Bearer {key}"},
        timeout=45,
    )
    if status == 200:
        results = resp.get("results") or resp.get("data") or []
        return True, results, None
    return False, [], f"BeatAPI HTTP {status} {str(resp)[:200]}"


def research_context(topic, keywords=""):
    """Construit un bloc de contexte frais pour le prompt de rédaction.
    Mode dégradé : retourne '' si BeatAPI indisponible — l'article reste
    générable sans sources externes."""
    if not configured():
        return ""
    ok, results, err = web_search(topic, limit=5)
    if not ok or not results:
        return ""
    lines = ["Sources récentes trouvées en ligne (à citer/paraphraser, ne pas inventer) :"]
    for r in results[:5]:
        title = r.get("title", "")
        url = r.get("url", "")
        desc = (r.get("description") or "")[:180]
        lines.append(f"- {title} ({url}) : {desc}")
    return "\n".join(lines)
