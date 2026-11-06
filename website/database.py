"""
database.py - SQLite database helpers for PREMEYFILES.

Tables
------
admins            administrator accounts (passwords are hashed)
api_tokens        login sessions used by the desktop admin application
categories        project categories
languages         programming-language tags
projects          the uploaded projects
project_languages which languages belong to which project
files             information about the stored source-code file of a project
downloads         one row for every download (download statistics)
settings          website settings (name, about text, allowed extensions ...)
messages          messages sent through the contact form
"""
import sqlite3

from flask import g
from werkzeug.security import generate_password_hash

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS admins (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS api_tokens (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id   INTEGER NOT NULL REFERENCES admins(id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS languages (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS projects (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    title          TEXT NOT NULL,
    description    TEXT NOT NULL DEFAULT '',
    category_id    INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    thumbnail      TEXT,
    download_count INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS project_languages (
    project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    language_id INTEGER NOT NULL REFERENCES languages(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, language_id)
);

CREATE TABLE IF NOT EXISTS files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL UNIQUE REFERENCES projects(id) ON DELETE CASCADE,
    stored_name   TEXT NOT NULL UNIQUE,
    original_name TEXT NOT NULL,
    extension     TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL DEFAULT 0,
    uploaded_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS downloads (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    downloaded_at TEXT NOT NULL DEFAULT (datetime('now')),
    ip_hash       TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,
    message    TEXT NOT NULL,
    is_read    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_projects_created ON projects(created_at);
CREATE INDEX IF NOT EXISTS idx_downloads_project ON downloads(project_id, downloaded_at);
"""

DEFAULT_SETTINGS = {
    "site_name": "PREMEYFILES",
    "tagline": "Source code, templates and development resources",
    "hero_title": "Download quality source code",
    "hero_subtitle": "Browse projects, templates and developer resources. "
                     "Free to explore, simple to download.",
    "about_text": "PREMEYFILES is a source-code distribution platform. "
                  "We collect useful projects, templates and development "
                  "resources in one clean place so developers can find "
                  "what they need and start building faster.",
    "contact_email": "",
    "footer_text": "Built for developers.",
    "max_upload_mb": str(config.DEFAULT_MAX_UPLOAD_MB),
    "allowed_extensions": config.DEFAULT_ALLOWED_EXTENSIONS,
}

DEFAULT_CATEGORIES = [
    ("Web Projects", "Websites, web apps and landing pages"),
    ("Python Scripts", "Python programs, bots and automation"),
    ("Templates", "Ready-to-use website and app templates"),
    ("Games", "Small games and game engines"),
    ("Mobile Apps", "Android, iOS and cross-platform apps"),
    ("Tools & Utilities", "Handy developer tools"),
    ("Databases", "SQL files and database designs"),
    ("Other", "Everything else"),
]

DEFAULT_LANGUAGES = [
    "Python", "JavaScript", "HTML/CSS", "PHP", "Java", "C++", "C", "SQL", "Other",
]


# ------------------------------------------------------------------ connection
def _connect():
    conn = sqlite3.connect(str(config.DATABASE_PATH), timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_db():
    """One database connection per web request."""
    if "db" not in g:
        g.db = _connect()
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    cur = get_db().execute(sql, args)
    rows = cur.fetchall()
    cur.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute(sql, args=()):
    """Run INSERT / UPDATE / DELETE and save it. Returns the new row id."""
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


# ------------------------------------------------------------------ setup
def init_db():
    """Create the database file, the tables and the default content."""
    config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.FILES_DIR.mkdir(parents=True, exist_ok=True)
    config.THUMBS_DIR.mkdir(parents=True, exist_ok=True)

    conn = _connect()
    try:
        try:
            conn.execute("PRAGMA journal_mode = WAL")
        except sqlite3.DatabaseError:
            pass
        conn.executescript(SCHEMA)

        for key, value in DEFAULT_SETTINGS.items():
            conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
        if conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            conn.executemany("INSERT INTO categories (name, description) VALUES (?, ?)", DEFAULT_CATEGORIES)
        if conn.execute("SELECT COUNT(*) FROM languages").fetchone()[0] == 0:
            conn.executemany("INSERT INTO languages (name) VALUES (?)", [(n,) for n in DEFAULT_LANGUAGES])
        conn.commit()
    finally:
        conn.close()


def hash_password(password):
    return generate_password_hash(password, method="pbkdf2:sha256:600000")


def create_or_update_admin(username, password):
    """Create an admin, or reset the password if the username already exists."""
    conn = _connect()
    try:
        row = conn.execute("SELECT id FROM admins WHERE username = ?", (username,)).fetchone()
        if row:
            conn.execute("UPDATE admins SET password_hash = ? WHERE id = ?", (hash_password(password), row["id"]))
            conn.execute("DELETE FROM api_tokens WHERE admin_id = ?", (row["id"],))
            action = "updated"
        else:
            conn.execute("INSERT INTO admins (username, password_hash) VALUES (?, ?)", (username, hash_password(password)))
            action = "created"
        conn.commit()
        return action
    finally:
        conn.close()


def admin_count():
    conn = _connect()
    try:
        return conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0]
    finally:
        conn.close()


def bootstrap_admin_from_env():
    """If there is no admin yet and ADMIN_USERNAME / ADMIN_PASSWORD are set in
    the environment, create that admin. Handy for online hosting."""
    if admin_count() > 0:
        return False
    if config.ADMIN_USERNAME and len(config.ADMIN_PASSWORD) >= config.MIN_PASSWORD_LENGTH:
        create_or_update_admin(config.ADMIN_USERNAME, config.ADMIN_PASSWORD)
        print("[PREMEYFILES] Admin account '%s' created from environment variables." % config.ADMIN_USERNAME)
        return True
    return False


# ------------------------------------------------------------------ settings
def get_settings():
    return {row["key"]: row["value"] for row in query("SELECT key, value FROM settings")}


def set_setting(key, value):
    execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
