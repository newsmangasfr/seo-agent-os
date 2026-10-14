# -*- coding: utf-8 -*-
"""Backend — façade historique + routes core (sites, articles, keys, stats).

Les anciennes routes de l'Agent OS d'origine sont conservées telles quelles
pour compatibilité ; les nouvelles apps (content, etc.) s'enregistrent
elles-mêmes dans core.router via apps/__init__.py.
"""
import json
import os

from core import db, router
from core.router import register

from core.paths import BASE_DIR
KEYS_FILE = __import__("core.paths", fromlist=["KEYS_FILE"]).KEYS_FILE

# les apps s'enregistrent au import
import apps  # noqa: E402,F401
import apps.auth  # noqa: E402,F401  (routes /api/auth/*)
import apps.tools  # noqa: E402,F401  (routes /api/tools/*)
from apps import wordpress  # noqa: E402


# ---------- Keys ----------
def load_keys():
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE) as f:
            return json.load(f)
    return {}


def save_keys(keys):
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)


# ---------- Routes historiques ----------

def get_sites(ctx, body):
    rows = db.fetchall("SELECT * FROM sites ORDER BY name")
    for r in rows:
        if r.get("wp_user") and r.get("wp_app_password"):
            res = wordpress.test_site(r)
            r["wp_status"] = "connected" if res["ok"] else f"error: {res.get('error', '?')[:60]}"
        else:
            r["wp_status"] = "no-credentials"
        r.pop("wp_app_password", None)
    return {"ok": True, "sites": rows}


def add_site(ctx, body):
    cur = db.execute(
        "INSERT OR IGNORE INTO sites (name, url, wp_user, wp_app_password, gsc_property, bing_site) VALUES (?,?,?,?,?,?)",
        (body.get("name"), body.get("url"), body.get("wp_user"),
         body.get("wp_app_password"), body.get("gsc_property"), body.get("bing_site")))
    return {"ok": cur.rowcount > 0, "id": cur.lastrowid}


def test_site(ctx, body):
    row = db.fetchone("SELECT * FROM sites WHERE id=?", (ctx["params"]["id"],))
    return wordpress.test_site(row) if row else {"ok": False, "error": "site introuvable"}


def delete_site(ctx, body):
    db.execute("DELETE FROM sites WHERE id=?", (ctx["params"]["id"],))
    return {"ok": True}


def get_articles(ctx, body):
    rows = db.fetchall("""
        SELECT a.*, s.name as site_name, s.url as site_url
        FROM articles a LEFT JOIN sites s ON a.site_id=s.id
        ORDER BY a.created_at DESC LIMIT 100""")
    return {"ok": True, "articles": rows}


def delete_article(ctx, body):
    db.execute("DELETE FROM articles WHERE id=?", (ctx["params"]["id"],))
    return {"ok": True}


def save_api_keys(ctx, body):
    keys = load_keys()
    for k, v in body.items():
        if v:
            keys[k] = v
    save_keys(keys)
    return {"ok": True, "saved": list(body.keys())}


def get_keys_status(ctx, body):
    keys = load_keys()
    return {"ok": True,
            "gsc_configured": bool(keys.get("gsc_service_account")),
            "bing_configured": bool(keys.get("bing_api_key")),
            "openrouter_configured": bool(keys.get("openrouter")),
            "beatapi_configured": bool(keys.get("beatapi"))}


def get_stats(ctx, body):
    sites = db.fetchone("SELECT COUNT(*) c FROM sites")["c"]
    arts = db.fetchone("SELECT COUNT(*) c FROM articles")["c"]
    published = db.fetchone("SELECT COUNT(*) c FROM articles WHERE wp_post_id IS NOT NULL")["c"]
    return {"ok": True, "sites": sites, "articles": arts, "published": published}


def xcloud_status(ctx, body):
    from providers import xcloud
    return xcloud.summary()


def xcloud_servers(ctx, body):
    from providers import xcloud
    if not xcloud.configured():
        return {"ok": False, "error": "token xCloud non configuré"}
    ok, data = xcloud.list_servers()
    if not ok:
        return {"ok": False, "error": data}
    return {"ok": True, "servers": data}


def xcloud_sites(ctx, body):
    from providers import xcloud
    if not xcloud.configured():
        return {"ok": False, "error": "token xCloud non configuré"}
    ok, data = xcloud.list_sites()
    if not ok:
        return {"ok": False, "error": data}
    return {"ok": True, "sites": data}


def xcloud_deploy(ctx, body):
    """POST /api/xcloud/deploy — déploie l'Agent OS sur un serveur.
    body : server_uuid, domain, repo_url, mode ('docker'|'nodejs'), dry_run(bool)"""
    from providers import xcloud
    if not xcloud.configured():
        return {"ok": False, "error": "token xCloud non configuré"}
    uuid = body.get("server_uuid")
    if not uuid:
        ok, servers = xcloud.list_servers()
        if not ok or not servers:
            return {"ok": False, "error": "aucun serveur trouvé — attache ton VPS Contabo dans le dashboard d'abord"}
        uuid = servers[0].get("uuid")
    mode = body.get("mode", "docker")
    dry = bool(body.get("dry_run", True))
    kwargs = dict(
        name=body.get("name", "agent-os"),
        domain=body.get("domain", ""),
        repository_url=body.get("repo_url", ""),
        branch=body.get("branch", "main"),
        dry_run=dry,
        env_content=body.get("env_content"),
    )
    if mode == "docker":
        ok, data, msg = xcloud.deploy_docker(uuid, **kwargs)
    else:
        ok, data, msg = xcloud.deploy_nodejs(uuid, **kwargs)
    if not ok:
        return {"ok": False, "error": msg, "guidance": data}
    return {"ok": True, "dry_run": dry, "data": data, "message": msg, "server_uuid": uuid, "mode": mode}


# ---------- GSC ----------
def gsc_status(ctx, body):
    from providers import gsc
    return {"ok": True, "configured": gsc.configured()}


def gsc_sites(ctx, body):
    from providers import gsc
    if not gsc.configured():
        return {"ok": False, "error": "compte de service GSC non configuré (importe la clé JSON)"}
    ok, data = gsc.list_sites()
    return {"ok": ok, "sites": data} if ok else {"ok": False, "error": data}


def gsc_summary(ctx, body):
    """GET /api/gsc/summary?property=sc-domain:xxx&days=28"""
    from providers import gsc
    if not gsc.configured():
        return {"ok": False, "error": "GSC non configuré"}
    prop = ctx["params"].get("property") or body.get("property")
    if not prop:
        return {"ok": False, "error": "propriété GSC requise"}
    ok, data = gsc.summary(prop, days=int(ctx["params"].get("days", 28)))
    return {"ok": ok, "data": data} if ok else {"ok": False, "error": data}


# ---------- Bing ----------
def bing_status(ctx, body):
    from providers import bing
    return {"ok": True, "configured": bing.configured()}


def bing_sites(ctx, body):
    from providers import bing
    if not bing.configured():
        return {"ok": False, "error": "clé Bing non configurée"}
    ok, data = bing.list_sites()
    return {"ok": ok, "sites": data} if ok else {"ok": False, "error": data}


def bing_traffic(ctx, body):
    from providers import bing
    if not bing.configured():
        return {"ok": False, "error": "Bing non configuré"}
    site_url = ctx["params"].get("site") or body.get("site")
    if not site_url:
        return {"ok": False, "error": "URL du site requise"}
    ok, data = bing.get_traffic(site_url)
    return {"ok": ok, "data": data} if ok else {"ok": False, "error": data}


LEGACY_ROUTES = [
    ("GET", r"/api/sites", get_sites),
    ("POST", r"/api/sites", add_site),
    ("POST", r"/api/sites/(?P<id>\d+)/test", test_site),
    ("DELETE", r"/api/sites/(?P<id>\d+)", delete_site),
    ("GET", r"/api/articles", get_articles),
    ("DELETE", r"/api/articles/(?P<id>\d+)", delete_article),
    ("POST", r"/api/keys", save_api_keys),
    ("GET", r"/api/keys", get_keys_status),
    ("GET", r"/api/stats", get_stats),
    ("GET", r"/api/xcloud/status", xcloud_status),
    ("GET", r"/api/xcloud/servers", xcloud_servers),
    ("GET", r"/api/xcloud/sites", xcloud_sites),
    ("POST", r"/api/xcloud/deploy", xcloud_deploy),
    ("GET", r"/api/gsc/status", gsc_status),
    ("GET", r"/api/gsc/sites", gsc_sites),
    ("GET", r"/api/gsc/summary\?property=(?P<property>[^&]+)(?:&days=(?P<days>\d+))?", gsc_summary),
    ("GET", r"/api/bing/status", bing_status),
    ("GET", r"/api/bing/sites", bing_sites),
    ("GET", r"/api/bing/traffic\?site=(?P<site>[^&]+)", bing_traffic),
]
register(LEGACY_ROUTES)

db.init_db()


def handle(request):
    """Point d'entrée unique — compatible avec l'ancien backend.handle()."""
    return router.handle(request)


if __name__ == "__main__":
    import sys
    req = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {"path": "/api/stats"}
    print(json.dumps(handle(req), indent=2, ensure_ascii=False))
