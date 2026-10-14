# -*- coding: utf-8 -*-
"""Sitemap — liens internes depuis le sitemap WordPress (règle SEO #1).

Récupère le sitemap d'un site, extrait les URLs, et suggère des liens
internes pertinents pour un article (matching par mots du titre/slug).
"""
import re
import xml.etree.ElementTree as ET

from core import http


def fetch_sitemap(site_url, max_urls=300):
    """Récupère les URLs du sitemap. Essaie plusieurs formats (Rank Math /
    ThinkRank / Yoast / WordPress) et AGRÈGE tous les sitemaps trouvés.
    Retourne (ok, [urls])."""
    import urllib.request
    base = site_url.rstrip("/")

    def _get(url):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AgentOS/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", "replace")
        except Exception:
            return None

    # 1. sitemap.xml peut être un index -> on collecte les sous-sitemaps
    all_urls, sitemap_urls = [], []
    raw = _get(f"{base}/sitemap.xml")
    if raw and ("<url" in raw or "<sitemapindex" in raw):
        for u in _extract_urls(raw):
            (sitemap_urls if u.endswith(".xml") else all_urls).append(u)
    # 2. formats connus en plus (posts, pages)
    for extra in ("/post-sitemap.xml", "/page-sitemap.xml", "/wp-sitemap-posts-post-1.xml"):
        r = _get(f"{base}{extra}")
        if r and "<url" in r:
            all_urls.extend(_extract_urls(r))
    # 3. on suit les sous-sitemaps découverts
    for su in sitemap_urls[:15]:
        r = _get(su)
        if r and "<url" in r:
            all_urls.extend(_extract_urls(r))
    # dédoublonnage
    seen, out = set(), []
    for u in all_urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return (True, out[:max_urls]) if out else (False, [])


def _extract_urls(xml_text):
    urls = []
    try:
        root = ET.fromstring(xml_text)
        for elem in root.iter():
            if elem.text and elem.text.strip().startswith("http"):
                urls.append(elem.text.strip())
    except ET.ParseError:
        # fallback regex si le XML est malformé
        urls = re.findall(r"https?://[^\s<>\"]+", xml_text)
    # dédoublonnage
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def suggest_internal_links(site_url, topic, keywords="", limit=5):
    """Suggère des liens internes pertinents pour un sujet.
    Matching : mots du titre/slug présents dans l'URL. Retourne (ok, [urls])."""
    ok, urls = fetch_sitemap(site_url)
    if not ok:
        return False, []
    terms = set(re.findall(r"\w+", f"{topic} {keywords}".lower()))
    terms = {t for t in terms if len(t) > 3}
    scored = []
    for u in urls:
        ul = u.lower()
        score = sum(1 for t in terms if t in ul)
        if score > 0:
            scored.append((score, u))
    scored.sort(key=lambda x: -x[0])
    return True, [u for _, u in scored[:limit]]
