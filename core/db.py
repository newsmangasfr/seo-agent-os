# -*- coding: utf-8 -*-
"""DB — accès SQLite (stdlib) avec migrations légères."""
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "seo_os.db")

_conn = None


def db():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
    return _conn


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
            provider TEXT,
            model TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            published_at TEXT,
            FOREIGN KEY(site_id) REFERENCES sites(id)
        );
        """)
        # migrations colonnes (ignore si déjà là)
        for stmt in (
            "ALTER TABLE articles ADD COLUMN provider TEXT",
            "ALTER TABLE articles ADD COLUMN model TEXT",
        ):
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError:
                pass


def fetchall(sql, args=()):
    return [dict(r) for r in db().execute(sql, args).fetchall()]


def fetchone(sql, args=()):
    r = db().execute(sql, args).fetchone()
    return dict(r) if r else None


def execute(sql, args=()):
    cur = db().execute(sql, args)
    db().commit()
    return cur
