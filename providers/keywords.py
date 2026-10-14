# -*- coding: utf-8 -*-
"""Keywords — recherche de mots-clés via Google Autocomplete (gratuit, sans clé).

Google Suggest renvoie les vraies recherches des utilisateurs : c'est la
meilleure source gratuite de mots-clés longue traîne avant de rédiger.
Endpoint public, aucune authentification.
"""
from core import http
import urllib.parse

SUGGEST_URL = "https://suggestqueries.google.com/complete/search"


def suggest(query, lang="fr", limit=10):
    """Suggestions Google pour une requête. Retourne (ok, [mots-clés])."""
    params = urllib.parse.urlencode({"client": "firefox", "hl": lang, "q": query})
    status, resp = http.get_json(f"{SUGGEST_URL}?{params}", timeout=15)
    if status == 200 and isinstance(resp, list) and len(resp) > 1:
        kws = [k for k in resp[1] if isinstance(k, str)]
        return True, kws[:limit]
    return False, []


def expand(seed, lang="fr", per_letter=3):
    """Expansion alphabetique : 'one piece a', 'one piece b'...
    Technique classique pour extraire la longue traîne. Retourne (ok, kws)."""
    results = []
    ok, base = suggest(seed, lang)
    if ok:
        results.extend(base)
    for letter in "abcdefghijklmnopqrstuvwxyz":
        ok, more = suggest(f"{seed} {letter}", lang, limit=per_letter)
        if ok:
            results.extend(more)
    # dédoublonnage en gardant l'ordre
    seen, unique = set(), []
    for k in results:
        kl = k.lower()
        if kl not in seen:
            seen.add(kl)
            unique.append(k)
    return True, unique


def research(topic, keywords="", lang="fr"):
    """Recherche complète pour un sujet : suggestions sur le sujet + chaque
    mot-clé fourni. Retourne (ok, {suggestions, expanded, questions})."""
    all_kw = []
    ok, s = suggest(topic, lang)
    if ok:
        all_kw.extend(s)
    for kw in [k.strip() for k in keywords.split(",") if k.strip()][:5]:
        ok, s2 = suggest(kw, lang)
        if ok:
            all_kw.extend(s2)
    # questions (comment, pourquoi, quand...)
    questions = [k for k in all_kw if k.lower().startswith(("comment", "pourquoi", "quand", "où", "quel", "quelle"))]
    seen, unique = set(), []
    for k in all_kw:
        kl = k.lower()
        if kl not in seen:
            seen.add(kl)
            unique.append(k)
    return True, {
        "suggestions": unique[:25],
        "questions": questions[:10],
        "count": len(unique),
    }
