"""
api.py - The secure admin API used by the PREMEYFILES ADMIN desktop app.

How authentication works
------------------------
1. The desktop app sends username + password to  POST /api/login
2. The server checks the password hash and returns a random token.
3. The desktop app sends that token in every later request:
       Authorization: Bearer <token>
4. Only a SHA-256 hash of the token is stored in the database.

Because the token is sent in a header (not a cookie), browsers cannot be
tricked into using it, so this API does not need CSRF tokens.
"""
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from functools import wraps

from flask import Blueprint, g, jsonify, request
from werkzeug.security import check_password_hash

import config
import database as db
import utils
from utils import ValidationError

api = Blueprint("api", __name__, url_prefix="/api")

# ------------------------------------------------------------------ login throttle
_failed = {}  # ip -> list of timestamps
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 300


def _client_ip():
    return request.remote_addr or "unknown"


def _too_many_attempts(ip):
    now = time.time()
    recent = [t for t in _failed.get(ip, []) if now - t < WINDOW_SECONDS]
    _failed[ip] = recent
    return len(recent) >= MAX_ATTEMPTS


def _record_failure(ip):
    _failed.setdefault(ip, []).append(time.time())


# ------------------------------------------------------------------ helpers
def error(message, status=400):
    return jsonify({"ok": False, "error": message}), status


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def admin_required(view):
    """Protect an API route: a valid, unexpired token is needed."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return error("Login required.", 401)
        token_hash = _hash_token(header[7:].strip())
        row = db.query(
            "SELECT t.id, t.expires_at, a.id AS admin_id, a.username "
            "FROM api_tokens t JOIN admins a ON a.id = t.admin_id WHERE t.token_hash = ?",
            (token_hash,), one=True,
        )
        if row is None:
            return error("Your session is invalid. Please log in again.", 401)
        if row["expires_at"] < datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"):
            db.execute("DELETE FROM api_tokens WHERE id = ?", (row["id"],))
            return error("Your session has expired. Please log in again.", 401)
        g.admin_id = row["admin_id"]
        g.admin_name = row["username"]
        g.token_id = row["id"]
        return view(*args, **kwargs)

    return wrapper


@api.errorhandler(ValidationError)
def _validation_error(exc):
    return error(str(exc), 400)


def _project_fields(partial=False):
    """Read and validate title / description / category / languages."""
    form = request.form
    data = {}
    if not partial or "title" in form:
        data["title"] = utils.clean_text(form.get("title"), 120, "Title", required=True, min_len=2)
    if not partial or "description" in form:
        data["description"] = utils.clean_text(form.get("description"), 5000, "Description")
    if not partial or "category_id" in form:
        data["category_id"] = utils.resolve_category_id(form.get("category_id"))
    if not partial or "language_ids" in form:
        data["language_ids"] = utils.resolve_language_ids(form.get("language_ids", ""))
    return data


def _set_languages(project_id, language_ids):
    db.execute("DELETE FROM project_languages WHERE project_id = ?", (project_id,))
    for lang_id in language_ids:
        db.execute(
            "INSERT OR IGNORE INTO project_languages (project_id, language_id) VALUES (?, ?)",
            (project_id, lang_id),
        )


# ------------------------------------------------------------------ auth
@api.post("/login")
def login():
    ip = _client_ip()
    if _too_many_attempts(ip):
        return error("Too many failed logins. Please wait 5 minutes and try again.", 429)

    body = request.get_json(silent=True) or {}
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", ""))

    admin = db.query("SELECT * FROM admins WHERE username = ?", (username,), one=True)
    # Always run a hash check so the response time does not reveal valid usernames.
    stored_hash = admin["password_hash"] if admin else db.hash_password("dummy-password")
    valid = check_password_hash(stored_hash, password)
    if not admin or not valid:
        _record_failure(ip)
        return error("Wrong username or password.", 401)

    _failed.pop(ip, None)
    token = secrets.token_urlsafe(40)
    expires = datetime.utcnow() + timedelta(hours=config.TOKEN_HOURS)
    db.execute("DELETE FROM api_tokens WHERE expires_at < ?", (datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),))
    db.execute(
        "INSERT INTO api_tokens (admin_id, token_hash, expires_at) VALUES (?, ?, ?)",
        (admin["id"], _hash_token(token), expires.strftime("%Y-%m-%d %H:%M:%S")),
    )
    return jsonify({"ok": True, "token": token, "username": admin["username"], "expires_hours": config.TOKEN_HOURS})


@api.post("/logout")
@admin_required
def logout():
    db.execute("DELETE FROM api_tokens WHERE id = ?", (g.token_id,))
    return jsonify({"ok": True})


@api.get("/me")
@admin_required
def me():
    return jsonify({"ok": True, "username": g.admin_name})


@api.post("/change-password")
@admin_required
def change_password():
    body = request.get_json(silent=True) or {}
    current, new = str(body.get("current", "")), str(body.get("new", ""))
    admin = db.query("SELECT * FROM admins WHERE id = ?", (g.admin_id,), one=True)
    if not check_password_hash(admin["password_hash"], current):
        return error("Your current password is wrong.", 400)
    if len(new) < config.MIN_PASSWORD_LENGTH:
        return error("New password must be at least %d characters." % config.MIN_PASSWORD_LENGTH)
    db.execute("UPDATE admins SET password_hash = ? WHERE id = ?", (db.hash_password(new), g.admin_id))
    # Log out every other session.
    db.execute("DELETE FROM api_tokens WHERE admin_id = ? AND id != ?", (g.admin_id, g.token_id))
    return jsonify({"ok": True})


# ------------------------------------------------------------------ dashboard
@api.get("/dashboard")
@admin_required
def dashboard():
    one = lambda sql: db.query(sql, one=True)[0]
    top = db.query(
        "SELECT id, title, download_count FROM projects ORDER BY download_count DESC, id DESC LIMIT 5"
    )
    recent = db.query(
        "SELECT id, title, created_at, download_count FROM projects ORDER BY created_at DESC, id DESC LIMIT 5"
    )
    per_day = db.query(
        "SELECT date(downloaded_at) AS day, COUNT(*) AS n FROM downloads "
        "WHERE downloaded_at >= datetime('now', '-7 days') GROUP BY day ORDER BY day"
    )
    return jsonify({
        "ok": True,
        "total_projects": one("SELECT COUNT(*) FROM projects"),
        "total_downloads": one("SELECT COALESCE(SUM(download_count), 0) FROM projects"),
        "downloads_today": one("SELECT COUNT(*) FROM downloads WHERE date(downloaded_at) = date('now')"),
        "total_categories": one("SELECT COUNT(*) FROM categories"),
        "total_languages": one("SELECT COUNT(*) FROM languages"),
        "total_storage_bytes": one("SELECT COALESCE(SUM(size_bytes), 0) FROM files"),
        "unread_messages": one("SELECT COUNT(*) FROM messages WHERE is_read = 0"),
        "top_projects": [dict(r) for r in top],
        "recent_projects": [dict(r) for r in recent],
        "downloads_per_day": [dict(r) for r in per_day],
    })


# ------------------------------------------------------------------ projects
@api.get("/projects")
@admin_required
def list_projects():
    q = (request.args.get("q") or "").strip()[:100]
    category = request.args.get("category", type=int)
    projects, total = utils.search_projects(q=q, category_id=category, sort=request.args.get("sort", "new"),
                                            limit=500, offset=0)
    return jsonify({"ok": True, "projects": projects, "total": total})


@api.get("/projects/<int:project_id>")
@admin_required
def get_project(project_id):
    project = utils.get_project(project_id)
    if not project:
        return error("Project not found.", 404)
    last = db.query(
        "SELECT date(downloaded_at) AS day, COUNT(*) AS n FROM downloads WHERE project_id = ? "
        "AND downloaded_at >= datetime('now', '-30 days') GROUP BY day ORDER BY day", (project_id,))
    project["downloads_last_30_days"] = [dict(r) for r in last]
    return jsonify({"ok": True, "project": project})


@api.post("/projects")
@admin_required
def create_project():
    fields = _project_fields()
    stored = utils.save_project_file(request.files.get("file"))
    thumb = None
    try:
        thumb = utils.save_thumbnail(request.files.get("thumbnail"))
        project_id = db.execute(
            "INSERT INTO projects (title, description, category_id, thumbnail) VALUES (?, ?, ?, ?)",
            (fields["title"], fields["description"], fields["category_id"], thumb),
        )
        db.execute(
            "INSERT INTO files (project_id, stored_name, original_name, extension, size_bytes) VALUES (?, ?, ?, ?, ?)",
            (project_id, stored["stored_name"], stored["original_name"], stored["extension"], stored["size_bytes"]),
        )
        _set_languages(project_id, fields["language_ids"])
    except Exception:
        # Do not leave orphan files behind if anything went wrong.
        utils.safe_delete(config.FILES_DIR, stored["stored_name"])
        if thumb:
            utils.safe_delete(config.THUMBS_DIR, thumb)
        raise
    return jsonify({"ok": True, "project": utils.get_project(project_id)}), 201


@api.put("/projects/<int:project_id>")
@admin_required
def update_project(project_id):
    project = db.query("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project:
        return error("Project not found.", 404)
    fields = _project_fields(partial=True)

    new_file = None
    new_thumb = None
    old_file = db.query("SELECT stored_name FROM files WHERE project_id = ?", (project_id,), one=True)
    try:
        if request.files.get("file") and request.files["file"].filename:
            new_file = utils.save_project_file(request.files["file"])
        if request.files.get("thumbnail") and request.files["thumbnail"].filename:
            new_thumb = utils.save_thumbnail(request.files["thumbnail"])

        title = fields.get("title", project["title"])
        description = fields.get("description", project["description"])
        category_id = fields["category_id"] if "category_id" in fields else project["category_id"]
        thumbnail = project["thumbnail"]
        remove_thumb = request.form.get("remove_thumbnail") == "1"
        if new_thumb:
            thumbnail = new_thumb
        elif remove_thumb:
            thumbnail = None

        db.execute(
            "UPDATE projects SET title = ?, description = ?, category_id = ?, thumbnail = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (title, description, category_id, thumbnail, project_id),
        )
        if "language_ids" in fields:
            _set_languages(project_id, fields["language_ids"])
        if new_file:
            db.execute(
                "UPDATE files SET stored_name = ?, original_name = ?, extension = ?, size_bytes = ?, "
                "uploaded_at = datetime('now') WHERE project_id = ?",
                (new_file["stored_name"], new_file["original_name"], new_file["extension"],
                 new_file["size_bytes"], project_id),
            )
    except Exception:
        if new_file:
            utils.safe_delete(config.FILES_DIR, new_file["stored_name"])
        if new_thumb:
            utils.safe_delete(config.THUMBS_DIR, new_thumb)
        raise

    # Only after the database is updated, remove the files that were replaced.
    if new_file and old_file:
        utils.safe_delete(config.FILES_DIR, old_file["stored_name"])
    if (new_thumb or request.form.get("remove_thumbnail") == "1") and project["thumbnail"]:
        utils.safe_delete(config.THUMBS_DIR, project["thumbnail"])
    return jsonify({"ok": True, "project": utils.get_project(project_id)})


@api.delete("/projects/<int:project_id>")
@admin_required
def delete_project(project_id):
    project = db.query("SELECT * FROM projects WHERE id = ?", (project_id,), one=True)
    if not project:
        return error("Project not found.", 404)
    file_row = db.query("SELECT stored_name FROM files WHERE project_id = ?", (project_id,), one=True)
    # Database first (so it disappears from the website at once), then the files.
    db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    if file_row:
        utils.safe_delete(config.FILES_DIR, file_row["stored_name"])
    if project["thumbnail"]:
        utils.safe_delete(config.THUMBS_DIR, project["thumbnail"])
    return jsonify({"ok": True})


# ------------------------------------------------------------------ categories
@api.get("/categories")
@admin_required
def list_categories():
    rows = db.query(
        "SELECT c.id, c.name, c.description, COUNT(p.id) AS projects "
        "FROM categories c LEFT JOIN projects p ON p.category_id = c.id GROUP BY c.id ORDER BY c.name"
    )
    return jsonify({"ok": True, "categories": [dict(r) for r in rows]})


@api.post("/categories")
@admin_required
def add_category():
    body = request.get_json(silent=True) or {}
    name = utils.clean_name(body.get("name"), "Category name")
    desc = utils.clean_text(body.get("description"), 200, "Description")
    if db.query("SELECT 1 FROM categories WHERE name = ? COLLATE NOCASE", (name,), one=True):
        return error("That category already exists.")
    cat_id = db.execute("INSERT INTO categories (name, description) VALUES (?, ?)", (name, desc))
    return jsonify({"ok": True, "id": cat_id}), 201


@api.put("/categories/<int:cat_id>")
@admin_required
def edit_category(cat_id):
    body = request.get_json(silent=True) or {}
    name = utils.clean_name(body.get("name"), "Category name")
    desc = utils.clean_text(body.get("description"), 200, "Description")
    if not db.query("SELECT 1 FROM categories WHERE id = ?", (cat_id,), one=True):
        return error("Category not found.", 404)
    if db.query("SELECT 1 FROM categories WHERE name = ? COLLATE NOCASE AND id != ?", (name, cat_id), one=True):
        return error("Another category already uses that name.")
    db.execute("UPDATE categories SET name = ?, description = ? WHERE id = ?", (name, desc, cat_id))
    return jsonify({"ok": True})


@api.delete("/categories/<int:cat_id>")
@admin_required
def delete_category(cat_id):
    if not db.query("SELECT 1 FROM categories WHERE id = ?", (cat_id,), one=True):
        return error("Category not found.", 404)
    # Projects in this category become "Uncategorized" (they are NOT deleted).
    db.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
    return jsonify({"ok": True})


# ------------------------------------------------------------------ languages
@api.get("/languages")
@admin_required
def list_languages():
    rows = db.query(
        "SELECT l.id, l.name, COUNT(pl.project_id) AS projects "
        "FROM languages l LEFT JOIN project_languages pl ON pl.language_id = l.id GROUP BY l.id ORDER BY l.name"
    )
    return jsonify({"ok": True, "languages": [dict(r) for r in rows]})


@api.post("/languages")
@admin_required
def add_language():
    name = utils.clean_name((request.get_json(silent=True) or {}).get("name"), "Language name")
    if db.query("SELECT 1 FROM languages WHERE name = ? COLLATE NOCASE", (name,), one=True):
        return error("That language tag already exists.")
    return jsonify({"ok": True, "id": db.execute("INSERT INTO languages (name) VALUES (?)", (name,))}), 201


@api.put("/languages/<int:lang_id>")
@admin_required
def edit_language(lang_id):
    name = utils.clean_name((request.get_json(silent=True) or {}).get("name"), "Language name")
    if not db.query("SELECT 1 FROM languages WHERE id = ?", (lang_id,), one=True):
        return error("Language not found.", 404)
    if db.query("SELECT 1 FROM languages WHERE name = ? COLLATE NOCASE AND id != ?", (name, lang_id), one=True):
        return error("Another language already uses that name.")
    db.execute("UPDATE languages SET name = ? WHERE id = ?", (name, lang_id))
    return jsonify({"ok": True})


@api.delete("/languages/<int:lang_id>")
@admin_required
def delete_language(lang_id):
    if not db.query("SELECT 1 FROM languages WHERE id = ?", (lang_id,), one=True):
        return error("Language not found.", 404)
    db.execute("DELETE FROM languages WHERE id = ?", (lang_id,))
    return jsonify({"ok": True})


# ------------------------------------------------------------------ settings
SETTING_LIMITS = {
    "site_name": 40, "tagline": 120, "hero_title": 80, "hero_subtitle": 240,
    "about_text": 3000, "contact_email": 120, "footer_text": 160,
}


@api.get("/settings")
@admin_required
def get_settings():
    return jsonify({
        "ok": True,
        "settings": db.get_settings(),
        "blocked_extensions": sorted(config.BLOCKED_EXTENSIONS),
        "hard_max_upload_mb": config.HARD_MAX_UPLOAD_MB,
    })


@api.put("/settings")
@admin_required
def update_settings():
    body = request.get_json(silent=True) or {}
    updates = {}
    for key, limit in SETTING_LIMITS.items():
        if key in body:
            updates[key] = utils.clean_text(str(body[key]), limit, key.replace("_", " ").title(),
                                            required=key in ("site_name", "hero_title"))
    if updates.get("contact_email"):
        updates["contact_email"] = utils.clean_email(updates["contact_email"])
    if "allowed_extensions" in body:
        updates["allowed_extensions"] = ",".join(utils.parse_extension_list(str(body["allowed_extensions"])))
    if "max_upload_mb" in body:
        try:
            mb = int(body["max_upload_mb"])
        except (TypeError, ValueError):
            raise ValidationError("Maximum upload size must be a whole number.")
        if not 1 <= mb <= config.HARD_MAX_UPLOAD_MB:
            raise ValidationError("Maximum upload size must be between 1 and %d MB." % config.HARD_MAX_UPLOAD_MB)
        updates["max_upload_mb"] = str(mb)
    for key, value in updates.items():
        db.set_setting(key, value)
    return jsonify({"ok": True, "settings": db.get_settings()})


# ------------------------------------------------------------------ messages
@api.get("/messages")
@admin_required
def list_messages():
    rows = db.query("SELECT * FROM messages ORDER BY created_at DESC, id DESC LIMIT 300")
    return jsonify({"ok": True, "messages": [dict(r) for r in rows]})


@api.post("/messages/<int:msg_id>/read")
@admin_required
def mark_read(msg_id):
    db.execute("UPDATE messages SET is_read = 1 WHERE id = ?", (msg_id,))
    return jsonify({"ok": True})


@api.delete("/messages/<int:msg_id>")
@admin_required
def delete_message(msg_id):
    db.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
    return jsonify({"ok": True})
