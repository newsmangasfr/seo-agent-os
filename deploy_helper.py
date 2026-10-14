# -*- coding: utf-8 -*-
"""deploy_helper.py — sauvegarde / restauration de la base autour d'un déploiement.

La base SQLite vit dans le volume Docker `agentos-data`, inaccessible
directement par l'API xCloud. Mais l'app expose une route admin pour
exporter/importer la base en base64. Ce helper :
  - backup  : GET  /api/admin/export-db  -> écrit seo_os_backup.db (hors git)
  - restore : POST /api/admin/import-db  <- relit seo_os_backup.db
  - recreate: supprime + recrée le site xCloud (clone propre du code)

Nécessite une session admin valide (cookie). En pratique, lance deploy.sh
qui orchestre le tout. La base de backup est stockée LOCALEMENT, jamais
dans le repo (elle contient les clés).
"""
import base64
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from providers import xcloud  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_FILE = os.path.join(BASE_DIR, "seo_os_backup.db")
COOKIE_FILE = os.path.join(BASE_DIR, ".deploy_cookie")
SITE_URL = "https://agentos.1wp.site"
SERVER_UUID = "038af358-2908-4ced-8972-218cd3232c31"
REPO = "https://github.com/newsmangasfr/seo-agent-os.git"


def _curl(method, url, cookie=None, data=None):
    cmd = ["curl", "-s", "-m", "60", "-X", method, url]
    if cookie:
        cmd += ["-b", cookie]
    if data is not None:
        cmd += ["-H", "Content-Type: application/json", "-d", json.dumps(data)]
    import subprocess
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.stdout


def backup():
    """Exporte la base depuis le serveur via l'API admin."""
    if not os.path.exists(COOKIE_FILE):
        print("  Pas de session. Connecte-toi d'abord (voir deploy.sh).")
        return False
    out = _curl("GET", f"{SITE_URL}/api/admin/export-db", cookie=COOKIE_FILE)
    try:
        d = json.loads(out)
    except Exception:
        print("  Réponse inattendue:", out[:120])
        return False
    if not d.get("ok"):
        print("  Export échoué:", d.get("error"))
        return False
    raw = base64.b64decode(d["db_base64"])
    with open(BACKUP_FILE, "wb") as f:
        f.write(raw)
    print(f"  Base sauvegardée ({len(raw)} octets) -> {os.path.basename(BACKUP_FILE)}")
    return True


def restore():
    """Réimporte la base sauvegardée sur le serveur frais."""
    if not os.path.exists(BACKUP_FILE):
        print("  Aucune sauvegarde locale à restaurer.")
        return False
    if not os.path.exists(COOKIE_FILE):
        print("  Pas de session pour restaurer.")
        return False
    with open(BACKUP_FILE, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    out = _curl("POST", f"{SITE_URL}/api/admin/import-db", cookie=COOKIE_FILE,
                data={"db_base64": b64})
    try:
        d = json.loads(out)
    except Exception:
        print("  Réponse inattendue:", out[:120])
        return False
    if d.get("ok"):
        print("  Base restaurée sur le serveur.")
        return True
    print("  Restauration échouée:", d.get("error"))
    return False


def recreate():
    """Supprime + recrée le site xCloud (clone propre du code à jour)."""
    ok, sites = xcloud.list_servers() and (True, xcloud.list_sites()[1])
    for s in xcloud.list_sites()[1]:
        if s.get("name", "").startswith("agentos"):
            from core import http
            http.request("DELETE", f"{xcloud.BASE_URL}/sites/{s['uuid']}",
                         headers=xcloud._auth(),
                         data={"delete_files": True, "delete_database": True, "delete_user": True},
                         timeout=60)
            print(f"  Site supprimé: {s['name']}")
    # attendre la suppression
    for _ in range(12):
        if not [s for s in xcloud.list_sites()[1] if s.get("name", "").startswith("agentos")]:
            break
        time.sleep(10)
    # recréer
    ok, data, msg = xcloud.deploy_docker(
        SERVER_UUID, name="agentos", domain="agentos",
        repository_url=REPO, branch="main", container_port=8000, host_port=8000,
        compose_file="docker-compose.yml", dry_run=False, staging=True)
    site = data.get("uuid")
    print(f"  Nouveau site: {data.get('domain')} ({site})")
    for _ in range(14):
        ok2, s, _ = xcloud.site_status(site)
        if not ok2:
            break
        if s.get("terminal"):
            print("  État:", s.get("deploy_state"))
            return s.get("deploy_state") == "deployed"
        time.sleep(15)
    return False


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    if action == "backup":
        sys.exit(0 if backup() else 1)
    elif action == "restore":
        sys.exit(0 if restore() else 1)
    elif action == "recreate":
        sys.exit(0 if recreate() else 1)
    else:
        print(__doc__)
        print("Actions: backup | restore | recreate")
