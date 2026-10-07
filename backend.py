#!/usr/bin/env python
"""Backend SEO Agent OS - API pour gestion sites WordPress, GSC, Bing."""
import json
import os
import sqlite3
import urllib.request
import urllib.error
import base64

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seo_os.db")
KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_keys.json")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            wp_user TEXT,
            wp_app_password TEXT,
            gsc_property TEXT,
            bing_site TEXT,
            added_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL,
            wp_post_id INTEGER,
            title TEXT NOT NULL,
            slug TEXT,
            content TEXT,
            meta_description TEXT,
            status TEXT DEFAULT 'draft',
            seo_title TEXT,
            score INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            published_at TEXT,
            FOREIGN KEY(site_id) REFERENCES sites(id)
        );
        """)


def load_keys():
    if os.path.exists(KEYS_FILE):
        with open(KEYS_FILE) as f:
            return json.load(f)
    return {}


def save_keys(keys):
    with open(KEYS_FILE, "w") as f:
        json.dump(keys, f, indent=2)


# ---------- WordPress helpers ----------
def wp_request(site, method, path, data=None):
    """Call site's WP REST API with app password auth."""
    base = site["url"].rstrip("/")
    auth = base64.b64encode(
        f'{site["wp_user"]}:{site["wp_app_password"]}'.encode()
    ).decode()
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        f"{base}/wp-json/wp/v2/{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/json",
            "User-Agent": "SEO-Agent-OS/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:
        return 0, {"error": str(e)}


def test_site(site):
    status, data = wp_request(site, "GET", "users/me?context=edit")
    if status == 200:
        return {"ok": True, "user": data.get("name"), "caps": list(data.get("capabilities", {}).keys())[:5]}
    return {"ok": False, "status": status, "error": data.get("message", data.get("error"))}


# ---------- Article generation (templates SEO, méthode du skill) ----------
def generate_article(site, topic, keywords, length):
    """Génère un article SEO structuré (base locale, à améliorer via agent)."""
    kw = [k.strip() for k in keywords.split(",") if k.strip()]
    kw_main = kw[0] if kw else topic
    n_words = {"500-800 mots (Court)": 700, "800-1500 mots (Standard)": 1200,
               "1500-2500 mots (Long)": 2000, "2500+ mots (Pilier)": 2800}.get(length, 1200)
    n_h2 = max(3, n_words // 350)
    intro = (f"{topic} est un sujet qui intéresse de plus en plus de lecteurs. "
             f"Dans cet article, nous allons voir en détail tout ce qu'il faut savoir "
             f"sur {kw_main}, avec des informations à jour et concrètes.")
    body = [intro, ""]
    for i in range(1, n_h2 + 1):
        body.append(f"## {kw_main if i==1 else kw[1] if len(kw)>1 and i==2 else f'Point {i}'}")
        body.append("")
        body.append(f"Voici ce qu'il faut retenir concernant {kw_main if i==1 else kw[1] if len(kw)>1 and i==2 else f'le point {i}'}.")
        body.append("")
    slug = topic.lower().replace(" ", "-")[:60]
    seo_title = topic[:60]
    meta_desc = f"Découvrez {kw_main} : analyse complète, dates et infos essentielles. Guide pratique et à jour."[:160]
    return {
        "title": topic,
        "slug": slug,
        "content": "\n".join(body),
        "seo_title": seo_title,
        "meta_description": meta_desc,
    }


# ---------- API Handlers ----------
def handle(request):
    init_db()
    path = request.get("path", "")
    method = request.get("method", "GET")
    body = request.get("body", {})

    if path == "/api/sites" and method == "GET":
        with db() as conn:
            rows = [dict(r) for r in conn.execute("SELECT * FROM sites ORDER BY name")]
        for r in rows:
            # Test status WP AVANT de retirer le secret de la réponse
            if r.get("wp_user") and r.get("wp_app_password"):
                res = test_site(r)
                r["wp_status"] = "connected" if res["ok"] else f"error: {res.get('error','?')[:60]}"
            else:
                r["wp_status"] = "no-credentials"
            r.pop("wp_app_password", None)
        return {"ok": True, "sites": rows}

    if path == "/api/sites" and method == "POST":
        with db() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO sites (name, url, wp_user, wp_app_password, gsc_property, bing_site) VALUES (?,?,?,?,?,?)",
                (body.get("name"), body.get("url"), body.get("wp_user"), body.get("wp_app_password"),
                 body.get("gsc_property"), body.get("bing_site")))
        return {"ok": cur.rowcount > 0, "id": cur.lastrowid}

    if path.startswith("/api/sites/") and "/test" in path and method == "POST":
        site_id = int(path.split("/")[3])
        with db() as conn:
            row = conn.execute("SELECT * FROM sites WHERE id=?", (site_id,)).fetchone()
        return test_site(row) if row else {"ok": False, "error": "site introuvable"}

    if path.startswith("/api/sites/") and method == "DELETE":
        site_id = int(path.split("/")[3])
        with db() as conn:
            conn.execute("DELETE FROM sites WHERE id=?", (site_id,))
        return {"ok": True}

    if path == "/api/articles" and method == "GET":
        with db() as conn:
            rows = [dict(r) for r in conn.execute("""
                SELECT a.*, s.name as site_name, s.url as site_url
                FROM articles a LEFT JOIN sites s ON a.site_id=s.id
                ORDER BY a.created_at DESC LIMIT 100""")]
        return {"ok": True, "articles": rows}

    if path == "/api/articles" and method == "POST":
        with db() as conn:
            site = conn.execute("SELECT * FROM sites WHERE id=?", (body.get("site_id"),)).fetchone()
        if not site:
            return {"ok": False, "error": "site introuvable"}
        art = generate_article(site, body.get("topic"), body.get("keywords", ""), body.get("length", "800-1500 mots (Standard)"))
        status = body.get("status", "draft")
        if status == "publish" and site.get("wp_user"):
            code, wp = wp_request(site, "POST", "posts", {
                "title": art["title"], "slug": art["slug"], "content": art["content"],
                "status": "publish", "meta": {"seopress_titles_title": art["seo_title"],
                                              "seopress_titles_desc": art["meta_description"]},
            })
            wp_id = wp.get("id") if code in (200, 201) else None
            link = wp.get("link") if wp_id else None
        else:
            wp_id, link, code = None, None, 0
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO articles (site_id, wp_post_id, title, slug, content, meta_description, status, seo_title) VALUES (?,?,?,?,?,?,?,?)",
                (site["id"], wp_id, art["title"], art["slug"], art["content"], art["meta_description"], status if wp_id else "draft", art["seo_title"]))
        return {"ok": True, "article_id": cur.lastrowid, "wp_id": wp_id, "wp_code": code, "wp_link": link, "article": art}

    if path == "/api/keys" and method == "POST":
        keys = load_keys()
        for k, v in body.items():
            if v:
                keys[k] = v
        save_keys(keys)
        return {"ok": True, "saved": list(body.keys())}

    if path == "/api/keys" and method == "GET":
        keys = load_keys()
        return {"ok": True,
                "gsc_configured": bool(keys.get("gsc_service_account")),
                "bing_configured": bool(keys.get("bing_api_key"))}

    if path == "/api/stats":
        with db() as conn:
            sites = conn.execute("SELECT COUNT(*) c FROM sites").fetchone()["c"]
            arts = conn.execute("SELECT COUNT(*) c FROM articles").fetchone()["c"]
            published = conn.execute("SELECT COUNT(*) c FROM articles WHERE wp_post_id IS NOT NULL").fetchone()["c"]
        return {"ok": True, "sites": sites, "articles": arts, "published": published}

    return {"ok": False, "error": f"route inconnue: {method} {path}"}


if __name__ == "__main__":
    import sys
    req = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {"path": "/api/stats"}
    print(json.dumps(handle(req), indent=2, ensure_ascii=False))
