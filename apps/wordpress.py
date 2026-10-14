# -*- coding: utf-8 -*-
"""WordPress — client REST partagé (app password)."""
import base64

from core import http


def wp_request(site, method, path, data=None):
    """site : dict avec url, wp_user, wp_app_password.
    Retourne (status, dict)."""
    base = site["url"].rstrip("/")
    auth = base64.b64encode(f'{site["wp_user"]}:{site["wp_app_password"]}'.encode()).decode()
    return http.request(
        method,
        f"{base}/wp-json/wp/v2/{path}",
        headers={"Authorization": f"Basic {auth}", "User-Agent": "AgentOS/1.0"},
        data=data,
        timeout=30,
        retries=1,
    )


def test_site(site):
    status, data = wp_request(site, "GET", "users/me?context=edit")
    if status == 200:
        return {"ok": True, "user": data.get("name")}
    return {"ok": False, "status": status, "error": data.get("message", data.get("error"))}


def publish_post(site, title, slug, content, seo_title, meta_desc, status="draft"):
    """Publie un article. SEOPress meta via 'meta'. Retourne (ok, wp_data, status)."""
    code, wp = wp_request(site, "POST", "posts", {
        "title": title,
        "slug": slug,
        "content": content,
        "status": status,
        "meta": {
            "seopress_titles_title": seo_title,
            "seopress_titles_desc": meta_desc,
        },
    })
    if code in (200, 201) and wp.get("id"):
        return True, wp, code
    return False, wp, code
