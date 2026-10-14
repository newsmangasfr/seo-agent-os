# -*- coding: utf-8 -*-
"""OpenRouter — modèles gratuits pour la génération de contenu.

Stratégie : liste ordonnée de modèles :free, on essaie le premier,
on bascule sur le suivant en cas d'échec (rate-limit, erreur 5xx).
Clé API lue dans api_keys.json (clé 'openrouter') ou $OPENROUTER_API_KEY.
"""
import os

from core import http
from core.paths import KEYS_FILE as _KF
from core.paths import BASE_DIR

import json

KEYS_FILE = _KF
BASE_URL = "https://openrouter.ai/api/v1"

# Modèles gratuits vérifiés via /api/v1/models (oct. 2026) et TESTÉS pour
# renvoyer du JSON direct. Les modèles "reasoning-only" (dots-3-note,
# nemotron-*, inkling*) sont EXCLUS : ils renvoient leur raisonnement dans
# 'reasoning' et content:null ou du texte non-JSON — inutilisables en mode
# response_format=json_object sans post-traitement lourd.
FREE_MODELS = [
    "google/gemma-4-31b-it:free",
    "poolside/laguna-s-2.1:free",
    "liquid/lfm-2.5-2.6b:free",
    "google/gemma-4-26b-a4b-it:free",
    "openrouter/free",
]

SYSTEM_PROMPT_FR = (
    "Tu es un rédacteur SEO expert francophone. Tu écris des articles complets, "
    "naturels, originaux, en français de France. Règles absolues : "
    "1) Structure H1 unique puis H2/H3 aérés, jamais de titres trop longs. "
    "2) Aucune phrase creuse du type 'dans cet article nous allons voir' — "
    "du contenu concret dès l'intro. "
    "3) Le mot-clé principal apparaît dans le H1, l'intro, un H2 et la conclusion, "
    "sans sur-optimisation. "
    "4) Dates et chiffres : France uniquement. "
    "5) Réponds UNIQUEMENT en JSON valide, sans texte avant/après, sans balises markdown."
)


def get_api_key():
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE) as f:
                return json.load(f).get("openrouter")
        except Exception:
            return None
    return None


def chat(messages, model=None, max_tokens=8000, temperature=0.7, json_mode=True):
    """Appelle OpenRouter avec fallback sur les modèles gratuits.
    Retourne (ok, content, model_used, error)."""
    key = get_api_key()
    if not key:
        return False, None, None, "clé OpenRouter absente (api_keys.json ou $OPENROUTER_API_KEY)"
    candidates = [model] if model else FREE_MODELS
    last_err = None
    for m in candidates:
        payload = {
            "model": m,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        status, resp = http.post_json(
            f"{BASE_URL}/chat/completions",
            data=payload,
            headers={"Authorization": f"Bearer {key}"},
            timeout=120,
            retries=1,
        )
        if status == 200 and resp.get("choices"):
            choice = resp["choices"][0]
            content = (choice.get("message") or {}).get("content")
            # Modèle reasoning ou réponse vide : on tente le modèle suivant
            # au lieu de planter sur content=None.
            if not content or not content.strip():
                # reasoning-only : on récupère le reasoning comme dernier recours
                reasoning = (choice.get("message") or {}).get("reasoning")
                if reasoning and reasoning.strip():
                    return True, reasoning, m, None
                last_err = f"{m}: contenu vide (content:null, reasoning vide)"
                continue
            return True, content, m, None
        last_err = f"{m}: HTTP {status} {str(resp.get('error', resp))[:200]}"
    return False, None, None, last_err


def _extract_json(text):
    """Extrait un objet JSON valide d'une réponse modèle, même entourée de
    texte ou tronquée (réparation : fences markdown, préambule, JSON
    incomplet refermé). Lève ValueError si aucun JSON récupérable."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # tente le premier {...} équilibré
    start = cleaned.find("{")
    if start == -1:
        raise ValueError("aucun JSON dans la réponse")
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(cleaned)):
        ch = cleaned[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(cleaned[start:i + 1])
    # JSON tronqué (max_tokens) : on tente de refermer les structures ouvertes
    raise ValueError(f"JSON tronqué ou invalide (début: {cleaned[start:start + 80]!r})")


def generate_article_json(topic, keywords, site_name, length="standard",
                          site_url=None, custom_instructions=""):
    """Génère un article complet structuré. Retourne dict article ou lève."""
    kw_list = [k.strip() for k in keywords.split(",") if k.strip()]
    kw_main = kw_list[0] if kw_list else topic
    n_words = {"court": 700, "standard": 1200, "long": 2000, "pilier": 2800}.get(length, 1200)

    user_prompt = (
        f"Écris un article SEO complet en français sur le sujet : {topic}\n"
        f"Mot-clé principal : {kw_main}\n"
        f"Mots-clés secondaires à intégrer naturellement : {', '.join(kw_list[1:]) or 'aucun'}\n"
        f"Longueur cible : environ {n_words} mots.\n"
        f"Site de publication : {site_name} ({site_url or '—'})\n"
        + (f"Instructions supplémentaires : {custom_instructions}\n" if custom_instructions else "")
        + "\nRéponds en JSON strict avec exactement ces champs :\n"
        '{"title": "...", "seo_title": "<=60 caractères, mot-clé devant", '
        '"slug": "...", "meta_description": "150-160 caractères", '
        '"content": "...", "internal_links": ["url1", "url2"], '
        '"tags": ["tag1", "tag2"]}\n'
        "Le champ content est en Markdown (H1 = titre, puis ## H2, ### H3), "
        "avec des paragraphes complets et concrets, pas de listes vides."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_FR},
        {"role": "user", "content": user_prompt},
    ]
    # budget tokens généreux : un JSON tronqué est inutilisable ; les modèles
    # gratuits plafonnent souvent la sortie, on demande large et on filtre.
    ok, content, model, err = chat(messages, max_tokens=min(16000, n_words * 4 + 2000))
    if not ok:
        raise RuntimeError(f"OpenRouter: {err}")
    try:
        art = _extract_json(content)
    except ValueError as e:
        raise RuntimeError(f"JSON illisible du modèle {model}: {e}")
    if not isinstance(art, dict) or not art.get("title") or not art.get("content"):
        raise RuntimeError(f"JSON incomplet du modèle {model}: clés title/content manquantes")
    art.setdefault("title", topic)
    art["_model"] = model
    return art


def list_free_models():
    """Récupère la liste live des modèles gratuits (info/UI)."""
    status, resp = http.get_json(f"{BASE_URL}/models", timeout=30)
    if status != 200:
        return []
    return [
        {"id": m["id"], "context": m.get("context_length")}
        for m in resp.get("data", [])
        if m.get("pricing", {}).get("prompt") == "0"
    ]
