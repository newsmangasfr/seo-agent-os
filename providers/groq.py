# -*- coding: utf-8 -*-
"""Groq — transcription audio (Whisper) + génération d'article depuis transcription.

Groq offre Whisper-large-v3 GRATUIT et ultra-rapide (~200x temps réel).
Workflow : upload audio -> transcription texte -> l'IA rédige un article.

Clé API : console.groq.com -> API Keys (gratuit).
Stockée dans api_keys.json (clé 'groq') ou $GROQ_API_KEY.
"""
import json
import os

from core import http
from core.paths import KEYS_FILE

BASE_URL = "https://api.groq.com/openai/v1"
WHISPER_MODEL = "whisper-large-v3"


def get_api_key():
    if os.environ.get("GROQ_API_KEY"):
        return os.environ["GROQ_API_KEY"]
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE) as f:
                return json.load(f).get("groq")
        except Exception:
            return None
    return None


def configured():
    return bool(get_api_key())


def transcribe(audio_bytes, filename="audio.mp3", language="fr"):
    """Transcrit un audio via Whisper. Retourne (ok, texte|erreur).
    audio_bytes : contenu binaire du fichier audio."""
    key = get_api_key()
    if not key:
        return False, "clé Groq absente (api_keys.json ou $GROQ_API_KEY)"
    # multipart/form-data (urllib ne le fait pas nativement -> construction manuelle)
    boundary = "----AgentOSBoundary" + os.urandom(16).hex()
    parts = []
    # champ model
    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"model\"\r\n\r\n{WHISPER_MODEL}\r\n".encode())
    if language:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"language\"\r\n\r\n{language}\r\n".encode())
    # fichier
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
        f"Content-Type: application/octet-stream\r\n\r\n".encode())
    parts.append(audio_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    # requête brute (http helper ne gère pas le binaire -> urllib direct)
    import urllib.request
    import urllib.error
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/audio/transcriptions",
            data=body, method="POST", headers=headers)
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read().decode())
        return True, result.get("text", "")
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
            return False, f"Groq HTTP {e.code}: {err.get('error', {}).get('message', str(err))[:200]}"
        except Exception:
            return False, f"Groq HTTP {e.code}"
    except Exception as e:
        return False, f"Groq: {str(e)[:200]}"
