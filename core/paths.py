# -*- coding: utf-8 -*-
"""Chemins de données — persistence.

RÈGLE : toutes les données persistantes (SQLite, clés API) vivent dans
DATA_DIR. En production (Docker) DATA_DIR est monté sur un volume nommé :
les données survivent aux redéploiements, mises à jour de thème et ajouts
d'options. En local, DATA_DIR = dossier du projet.
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("AGENTOS_DATA_DIR") or BASE_DIR

os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "seo_os.db")
KEYS_FILE = os.path.join(DATA_DIR, "api_keys.json")
