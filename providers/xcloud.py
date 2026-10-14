# -*- coding: utf-8 -*-
"""xCloud.host — pilotage de serveurs/sites par API (Sanctum Bearer).

Spec officielle (188 endpoints) : https://app.xcloud.host/api/v1/openapi.json
Auth : Personal Access Token (Settings → Developers → API Tokens).
Scopes utiles : read:servers, write:servers, read:sites, write:sites.

IMPORTANT — limitations connues :
- Un serveur BYO (Contabo) s'attache UNE FOIS à la main dans le dashboard
  (Other Providers). L'API ne permet pas de connecter un serveur externe.
- Pas de webhooks sortants : on interroge (poll) les endpoints de progression.
- Ton app Python (port 8000) se déploie via la variante Docker de sites/git.
- Rate limit : 60 req/min authentifié (429 + Retry-After au-delà).
"""
import json
import os

from core import http

BASE_URL = "https://app.xcloud.host/api/v1"
from core.paths import KEYS_FILE


def get_token():
    """Token depuis api_keys.json ('xcloud') ou $XCLOUD_TOKEN (ton .env existant)."""
    if os.environ.get("XCLOUD_TOKEN"):
        return os.environ["XCLOUD_TOKEN"]
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE) as f:
                return json.load(f).get("xcloud")
        except Exception:
            return None
    return None


def configured():
    return bool(get_token())


def _auth():
    return {"Authorization": f"Bearer {get_token()}", "Accept": "application/json"}


def _get(path, **kw):
    return http.get_json(f"{BASE_URL}{path}", headers=_auth(), timeout=30, **kw)


def _post(path, data=None, extra_headers=None, **kw):
    headers = dict(_auth())
    if extra_headers:
        headers.update(extra_headers)
    return http.post_json(f"{BASE_URL}{path}", data=data or {}, headers=headers, timeout=60, **kw)


def _unwrap(status, resp):
    """Enveloppe xCloud : {success, message, data}. Retourne (ok, data, message)."""
    if status == 200 or status == 201 or status == 202:
        return True, resp.get("data", resp), resp.get("message", "")
    return False, None, resp.get("message") or str(resp)[:200]


# ---------- Health ----------

def health():
    """GET /health — public, vérifie que l'API répond."""
    status, resp = http.get_json(f"{BASE_URL}/health", timeout=15)
    return status == 200 and resp.get("status") == "ok", resp


# ---------- Servers ----------

def list_servers(status_filter=None):
    """GET /servers — liste paginée (on prend la page 1, 100 max)."""
    q = "?per_page=100"
    if status_filter:
        q += f"&status={status_filter}"
    st, resp = _get(f"/servers{q}")
    ok, data, msg = _unwrap(st, resp)
    if not ok:
        return False, msg
    return True, data.get("items", [])


def get_server(uuid):
    """GET /servers/{uuid} — détail + capacités."""
    st, resp = _get(f"/servers/{uuid}")
    ok, data, msg = _unwrap(st, resp)
    return (True, data, msg) if ok else (False, None, msg)


def provisioning_progress(uuid):
    """GET /servers/{uuid}/provisioning-progress — suivi provisioning."""
    st, resp = _get(f"/servers/{uuid}/provisioning-progress")
    ok, data, msg = _unwrap(st, resp)
    return (True, data, msg) if ok else (False, None, msg)


def monitoring(uuid):
    """GET /servers/{uuid}/monitoring — CPU/RAM/disk temps réel."""
    st, resp = _get(f"/servers/{uuid}/monitoring")
    ok, data, msg = _unwrap(st, resp)
    return (True, data, msg) if ok else (False, None, msg)


def server_plans():
    """GET /servers/plans — plans (pour info UI)."""
    st, resp = _get("/servers/plans")
    ok, data, msg = _unwrap(st, resp)
    return (True, data, msg) if ok else (False, None, msg)


# ---------- Sites & déploiement ----------

def deploy_docker(uuid, name, domain, repository_url, branch="main",
                  container_port=8000, host_port=8000, env_content=None,
                  compose_file="docker-compose.yml", dry_run=True,
                  staging=False):
    """POST /servers/{uuid}/sites/git/docker — déploie une app conteneurisée.

    C'est LA voie pour l'Agent OS (Python stdlib + SQLite, pas de stack natif).
    - repository_url : URL publique HTTPS du repo git
    - container_port : port exposé par le conteneur (8000 pour server.py)
    - host_port : port publié sur l'hôte (1024-65535)
    - env_content : contenu du .env à écrire côté serveur (mode dégradé si None)
    - staging=True : domaine de démo xCloud (sous-domaine *.xc1.app auto,
      aucun DNS à configurer). staging=False : domaine live (A record requis).
    - dry_run=True par défaut : 200 + would_create, ne crée rien.
    Retourne (ok, data, message)."""
    payload = {
        "name": name,
        "repository": {"url": repository_url, "branch": branch},
        "domain": {
            "mode": "staging" if staging else "live",
            "name": name if staging else domain,
        },
        "port": host_port,
        "docker": {
            "mode": "compose",
            "compose_file": compose_file,
            "container_port": container_port,
        },
        "dry_run": bool(dry_run),
    }
    if not staging and domain:
        payload["domain"]["name"] = domain
    if env_content:
        payload["env_file_content"] = env_content
    st, resp = _post(f"/servers/{uuid}/sites/git/docker", data=payload)
    ok, data, msg = _unwrap(st, resp)
    if not ok:
        # 4xx git : errors{code, next_actions[], dashboard_url}
        errs = resp.get("errors", {})
        return False, errs, errs.get("code") or msg
    return True, data, msg


def deploy_nodejs(uuid, name, domain, repository_url, branch="main",
                  start_command="python server.py", port=8000,
                  build_command=None, install_command=None, env_content=None,
                  dry_run=True):
    """POST /servers/{uuid}/sites/git — variante nodejs (fallback si pas Docker).

    Utile si le serveur n'a pas Docker : xCloud lance la commande de démarrage
    et proxifie. Moins isolé mais fonctionne pour un process Python simple.
    Retourne (ok, data, message)."""
    payload = {
        "site_type": "nodejs",
        "name": name,
        "repository": {"url": repository_url, "branch": branch},
        "domain": {"mode": "live", "name": domain},
        "node_version": "22",
        "serving_mode": "ssr",
        "start_command": start_command,
        "port": port,
        "dry_run": bool(dry_run),
    }
    if build_command:
        payload["build_command"] = build_command
    if install_command:
        payload["install_command"] = install_command
    if env_content:
        payload["env_file_content"] = env_content
    st, resp = _post(f"/servers/{uuid}/sites/git", data=payload)
    ok, data, msg = _unwrap(st, resp)
    if not ok:
        errs = resp.get("errors", {})
        return False, errs, errs.get("code") or msg
    return True, data, msg


def list_sites():
    """GET /sites — tous les sites de l'équipe."""
    st, resp = _get("/sites?per_page=100")
    ok, data, msg = _unwrap(st, resp)
    if not ok:
        return False, msg
    return True, data.get("items", [])


def site_status(site_uuid):
    """GET /sites/{uuid}/status — endpoint de polling (poll_after_seconds)."""
    st, resp = _get(f"/sites/{site_uuid}/status")
    ok, data, msg = _unwrap(st, resp)
    return (True, data, msg) if ok else (False, None, msg)


def redeploy(site_uuid):
    """POST /sites/{uuid}/git/deploy — 202 task_uuid (409 si déploiement en cours)."""
    st, resp = _post(f"/sites/{site_uuid}/git/deploy")
    ok, data, msg = _unwrap(st, resp)
    return (True, data, msg) if ok else (False, None, msg)


def wait_site_ready(site_uuid, timeout_s=900, interval=15):
    """Poll GET /sites/{uuid}/status jusqu'à terminal.
    Retourne (ok, data_final)."""
    import time
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        ok, data, msg = site_status(site_uuid)
        if not ok:
            return False, {"error": msg}
        last = data
        if data.get("terminal"):
            failed = data.get("failed_steps") or []
            ssl_blocked = data.get("ssl", {}).get("serving_blocked")
            if failed or ssl_blocked:
                return False, data
            return True, data
        time.sleep(min(interval, 30))
    return False, {"error": "timeout", "last": last}


# ---------- Résumé pour l'UI ----------

def summary():
    """État global pour le dashboard : health, serveurs, sites."""
    if not configured():
        return {"ok": True, "configured": False}
    h, _ = health()
    ok_s, servers = list_servers()
    ok_sites, sites = list_sites()
    return {
        "ok": True,
        "configured": True,
        "api_healthy": h,
        "servers": servers if ok_s else [],
        "servers_error": None if ok_s else servers,
        "sites": sites if ok_sites else [],
        "sites_error": None if ok_sites else sites,
    }
