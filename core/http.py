# -*- coding: utf-8 -*-
"""HTTP — client urllib avec timeout, retry et JSON helpers."""
import json
import time
import urllib.error
import urllib.request

DEFAULT_TIMEOUT = 60
UA = "AgentOS/1.0 (+https://newsmangas.com)"


def request(method, url, headers=None, data=None, timeout=DEFAULT_TIMEOUT, retries=1):
    """Requête HTTP. Retourne (status, body_dict). Retry sur erreur réseau."""
    headers = dict(headers or {})
    headers.setdefault("User-Agent", UA)
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers.setdefault("Content-Type", "application/json")
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=body, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
                try:
                    return resp.status, json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    return resp.status, {"raw": raw}
        except urllib.error.HTTPError as e:
            try:
                payload = json.loads(e.read().decode("utf-8", "replace"))
            except Exception:
                payload = {"error": str(e)}
            return e.code, payload
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    return 0, {"error": str(last_err)}


def get_json(url, headers=None, **kw):
    return request("GET", url, headers=headers, **kw)


def post_json(url, data, headers=None, **kw):
    return request("POST", url, headers=headers, data=data, **kw)
