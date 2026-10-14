# -*- coding: utf-8 -*-
"""Google Search Console — lecture des données via compte de service.

Auth : compte de service Google (JSON) stocké dans api_keys.json
(clé 'gsc_service_account'). La clé doit être ajoutée comme utilisateur
de la propriété GSC (lecture suffit).

API : Search Console API v1
  - searchanalytics.query : clics/impressions/CTR/position
  - sites.list : propriétés accessibles

Aucune dépendance externe : JWT signé à la main (HS256 avec la clé privée
RSA du compte de service) via la stdlib n'est PAS possible directement —
on utilise l'échange OAuth2 JWT-bearer avec urllib + la signature RSA
faite par... en fait, signer un RS256 nécessite une lib crypto.

DÉCISION : la signature RS256 du JWT nécessite `cryptography` (pip).
On tente l'import ; si absent, on renvoie une erreur claire invitant à
installer le paquet. C'est la SEULE dépendance externe du projet, et
elle est optionnelle (le reste tourne sans).
"""
import json
import os
import time
import urllib.parse

from core import http

from core.paths import KEYS_FILE
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
API_BASE = "https://searchconsole.googleapis.com/webmasters/v3"

_token_cache = {"token": None, "exp": 0}


def _service_account():
    """Retourne le dict du compte de service ou None."""
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE) as f:
                sa = json.load(f).get("gsc_service_account")
                if isinstance(sa, str):
                    sa = json.loads(sa)
                return sa
        except Exception:
            return None
    return None


def configured():
    sa = _service_account()
    return bool(sa and sa.get("private_key"))


def _make_jwt(sa):
    """Crée un JWT RS256 signé pour l'échange OAuth2 (nécessite cryptography)."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        import base64
    except ImportError:
        raise RuntimeError(
            "Le paquet 'cryptography' est requis pour Google Search Console. "
            "Installe-le : pip install cryptography")

    def b64(data):
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": sa["client_email"],
        "scope": SCOPE,
        "aud": TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }
    signing_input = f"{b64(json.dumps(header).encode())}.{b64(json.dumps(claims).encode())}".encode()

    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    return f"{signing_input.decode()}.{b64(signature)}"


def get_access_token():
    """Obtient (et cache) un token d'accès OAuth2. Retourne (ok, token|err)."""
    if _token_cache["token"] and _token_cache["exp"] > time.time() + 60:
        return True, _token_cache["token"]
    sa = _service_account()
    if not sa:
        return False, "compte de service GSC non configuré"
    try:
        jwt = _make_jwt(sa)
    except Exception as e:
        return False, str(e)
    status, resp = http.post_json(TOKEN_URL, data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt,
    }, timeout=30)
    if status == 200 and resp.get("access_token"):
        _token_cache["token"] = resp["access_token"]
        _token_cache["exp"] = time.time() + resp.get("expires_in", 3600)
        return True, resp["access_token"]
    return False, f"OAuth2 echec HTTP {status}: {str(resp)[:150]}"


def _auth_headers():
    ok, tok = get_access_token()
    if not ok:
        raise RuntimeError(tok)
    return {"Authorization": f"Bearer {tok}"}


def list_sites():
    """GET /sites — propriétés accessibles. Retourne (ok, sites|err)."""
    try:
        headers = _auth_headers()
    except RuntimeError as e:
        return False, str(e)
    status, resp = http.get_json(f"{API_BASE}/sites", headers=headers, timeout=30)
    if status == 200:
        return True, resp.get("siteEntry", [])
    return False, f"HTTP {status}: {str(resp)[:150]}"


def query(property_url, start_date, end_date, dimensions=("query", "page"),
          row_limit=25):
    """POST /sites/{site}/searchanalytics/query — données de recherche.
    dimensions : 'query', 'page', 'date', 'country', 'device'
    Retourne (ok, rows|err)."""
    try:
        headers = _auth_headers()
    except RuntimeError as e:
        return False, str(e)
    url = f"{API_BASE}/sites/{urllib.parse.quote(property_url, safe='')}/searchanalytics/query"
    body = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": list(dimensions),
        "rowLimit": row_limit,
    }
    status, resp = http.post_json(url, data=body, headers=headers, timeout=45)
    if status == 200:
        return True, resp.get("rows", [])
    return False, f"HTTP {status}: {str(resp)[:200]}"


def summary(property_url, days=28):
    """Résumé global + top requêtes + top pages sur N jours.
    Retourne (ok, dict|err)."""
    from datetime import datetime, timedelta
    end = datetime.utcnow().date()
    start = end - timedelta(days=days)
    sd, ed = start.isoformat(), end.isoformat()

    ok, total = query(property_url, sd, ed, dimensions=(), row_limit=1)
    if not ok:
        return False, total
    ok_q, queries = query(property_url, sd, ed, dimensions=("query",), row_limit=20)
    ok_p, pages = query(property_url, sd, ed, dimensions=("page",), row_limit=20)
    return True, {
        "period": {"start": sd, "end": ed, "days": days},
        "totals": total[0] if total else {},
        "top_queries": queries if ok_q else [],
        "top_pages": pages if ok_p else [],
    }
