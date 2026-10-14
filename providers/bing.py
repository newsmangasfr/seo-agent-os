# -*- coding: utf-8 -*-
"""Bing Webmaster Tools — lecture des données via clé API.

Auth : clé API simple (Bing Webmaster → Settings → API Access).
Beaucoup plus simple que GSC : juste un header, pas d'OAuth.

Clé stockée dans api_keys.json (clé 'bing_api_key') ou $BING_API_KEY.

API : https://ssl.bing.com/webmaster/api.svc/json/...
Documentation : https://learn.microsoft.com/en-us/bingwebmaster/
"""
import json
import os

from core import http

KEYS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api_keys.json")
BASE_URL = "https://ssl.bing.com/webmaster/api.svc/json"


def get_api_key():
    if os.environ.get("BING_API_KEY"):
        return os.environ["BING_API_KEY"]
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE) as f:
                return json.load(f).get("bing_api_key")
        except Exception:
            return None
    return None


def configured():
    return bool(get_api_key())


def _headers():
    return {"Authorization": f"Bearer {get_api_key()}"}


def _get(endpoint):
    """Appelle un endpoint JSON Bing. Retourne (ok, data|err)."""
    if not configured():
        return False, "clé Bing absente"
    status, resp = http.get_json(f"{BASE_URL}/{endpoint}", headers=_headers(), timeout=30)
    if status == 200:
        return True, resp.get("d", resp)
    return False, f"HTTP {status}: {str(resp)[:150]}"


def list_sites():
    """GET /GetUserSites — sites vérifiés. Retourne (ok, sites|err)."""
    return _get("GetUserSites")


def get_stats(site_url, days=28):
    """Récupère les stats de trafic d'un site.
    Bing expose GetQueryStats / GetPageStats. Retourne (ok, stats|err)."""
    ok, data = _get(f"GetQueryStats?siteUrl={site_url}")
    if not ok:
        # certains endpoints nécessitent des params supplémentaires ;
        # on retente sans pour au moins lister les requêtes
        ok2, data2 = _get(f"GetRankStats?siteUrl={site_url}")
        if ok2:
            return True, {"rank": data2}
        return False, data
    return True, {"queries": data}


def get_crawl_issues(site_url):
    """GET /GetCrawlIssues — problèmes d'exploration. Retourne (ok, issues|err)."""
    return _get(f"GetCrawlIssues?siteUrl={site_url}")


def get_link_counts(site_url):
    """GET /GetLinkCounts — nombre de liens entrants. Retourne (ok, data|err)."""
    return _get(f"GetLinkCounts?siteUrl={site_url}")


def get_traffic(site_url):
    """Vue d'ensemble : liens + crawl. Retourne (ok, dict|err)."""
    ok_l, links = get_link_counts(site_url)
    ok_c, crawl = get_crawl_issues(site_url)
    return True, {
        "links": links if ok_l else None,
        "crawl_issues_count": (len(crawl) if ok_c and isinstance(crawl, list) else None),
    }
