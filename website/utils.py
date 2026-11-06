"""
utils.py - Validation, secure file saving and project helpers.
"""
import hashlib
import os
import re
import uuid
from datetime import datetime

from werkzeug.utils import secure_filename

import config
import database as db

STORED_NAME_RE = re.compile(r"^[a-f0-9]{32}\.[a-z0-9]{1,10}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
TAG_NAME_RE = re.compile(r"^[A-Za-z0-9 +#.\-/&]{1,40}$")
EXT_RE = re.compile(r"^[a-z0-9]{1,10}$")


class ValidationError(ValueError):
    """An error message that is safe to show to the user."""


# ------------------------------------------------------------------ text
def clean_text(value, max_len, label="Value", required=False, min_len=0):
    value = (value or "").replace("\x00", "").strip()
    # remove control characters except newline / tab
    value = "".join(ch for ch in value if ch in "\n\t" or ord(ch) >= 32)
    if required and not value:
        raise ValidationError("%s is required." % label)
    if value and len(value) < min_len:
        raise ValidationError("%s must be at least %d characters." % (label, min_len))
    if len(value) > max_len:
        raise ValidationError("%s must be at most %d characters." % (label, max_len))
    return value


def clean_name(value, label="Name"):
    value = clean_text(value, 40, label, required=True)
    if not TAG_NAME_RE.match(value):
        raise ValidationError(
            "%s may only contain letters, numbers, spaces and + # . - / &" % label
        )
    return value


def clean_email(value):
    value = clean_text(value, 120, "Email", required=True)
    if not EMAIL_RE.match(value):
        raise ValidationError("Please enter a valid email address.")
    return value


def hash_ip(ip):
    """Store only a salted hash of the visitor's IP address (privacy)."""
    return hashlib.sha256((config.SECRET_KEY + (ip or "")).encode()).hexdigest()[:24]


# ------------------------------------------------------------------ settings
def allowed_extensions():
    raw = db.get_settings().get("allowed_extensions", config.DEFAULT_ALLOWED_EXTENSIONS)
    result = {e.strip().lower().lstrip(".") for e in raw.split(",") if e.strip()}
    return {e for e in result if EXT_RE.match(e)} - config.BLOCKED_EXTENSIONS


def max_upload_bytes():
    try:
        mb = int(db.get_settings().get("max_upload_mb", config.DEFAULT_MAX_UPLOAD_MB))
    except ValueError:
        mb = config.DEFAULT_MAX_UPLOAD_MB
    mb = max(1, min(mb, config.HARD_MAX_UPLOAD_MB))
    return mb * 1024 * 1024


def parse_extension_list(raw):
    """Turn 'zip, .rar,7z' into a clean sorted list. Raises on bad input."""
    items = []
    for part in (raw or "").split(","):
        ext = part.strip().lower().lstrip(".")
        if not ext:
            continue
        if not EXT_RE.match(ext):
            raise ValidationError("'%s' is not a valid file extension." % part.strip())
        if ext in config.BLOCKED_EXTENSIONS:
            raise ValidationError("'.%s' files can never be allowed (executable type)." % ext)
        if ext not in items:
            items.append(ext)
    if not items:
        raise ValidationError("At least one file extension must be allowed.")
    return items


# ------------------------------------------------------------------ files
def _extension_of(filename):
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower().strip()


def safe_delete(directory, stored_name):
    """Delete a stored file only if it really lives inside `directory`."""
    if not stored_name or not STORED_NAME_RE.match(stored_name):
        return False
    base = directory.resolve()
    target = (base / stored_name).resolve()
    if base not in target.parents:
        return False
    try:
        target.unlink()
        return True
    except FileNotFoundError:
        return False
    except OSError as error:
        print("[PREMEYFILES] Could not delete %s: %s" % (target, error))
        return False


def save_project_file(file_storage):
    """Validate and save an uploaded source-code file.
    Returns a dict with stored_name, original_name, extension, size_bytes."""
    if file_storage is None or not file_storage.filename:
        raise ValidationError("Please choose a file to upload.")

    ext = _extension_of(file_storage.filename)
    if not ext:
        raise ValidationError("The file has no extension.")
    if ext in config.BLOCKED_EXTENSIONS:
        raise ValidationError("'.%s' files are not allowed for security reasons." % ext)
    allowed = allowed_extensions()
    if ext not in allowed:
        raise ValidationError(
            "'.%s' files are not allowed. Allowed types: %s" % (ext, ", ".join(sorted(allowed)))
        )

    original = secure_filename(file_storage.filename)
    if not original or _extension_of(original) != ext:
        original = "download.%s" % ext

    stored = "%s.%s" % (uuid.uuid4().hex, ext)
    config.FILES_DIR.mkdir(parents=True, exist_ok=True)
    path = config.FILES_DIR / stored
    file_storage.save(str(path))

    size = os.path.getsize(path)
    if size == 0:
        safe_delete(config.FILES_DIR, stored)
        raise ValidationError("The uploaded file is empty.")
    if size > max_upload_bytes():
        safe_delete(config.FILES_DIR, stored)
        raise ValidationError(
            "The file is too large (limit is %d MB)." % (max_upload_bytes() // (1024 * 1024))
        )
    return {"stored_name": stored, "original_name": original, "extension": ext, "size_bytes": size}


def _image_type(header):
    """Detect the real image type from the first bytes of the file."""
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if header.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if header.startswith(b"GIF87a") or header.startswith(b"GIF89a"):
        return "gif"
    if header[:4] == b"RIFF" and header[8:12] == b"WEBP":
        return "webp"
    return None


def save_thumbnail(file_storage):
    """Validate and save a thumbnail image. Returns the stored file name."""
    if file_storage is None or not file_storage.filename:
        return None
    ext = _extension_of(file_storage.filename)
    if ext not in config.THUMBNAIL_EXTENSIONS:
        raise ValidationError("Thumbnail must be a PNG, JPG, GIF or WEBP image.")

    header = file_storage.stream.read(16)
    file_storage.stream.seek(0)
    real_type = _image_type(header)
    if real_type is None:
        raise ValidationError("The thumbnail is not a valid image file.")

    stored = "%s.%s" % (uuid.uuid4().hex, real_type)
    config.THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    path = config.THUMBS_DIR / stored
    file_storage.save(str(path))
    if os.path.getsize(path) > config.MAX_THUMBNAIL_MB * 1024 * 1024:
        safe_delete(config.THUMBS_DIR, stored)
        raise ValidationError("Thumbnail is too large (limit is %d MB)." % config.MAX_THUMBNAIL_MB)
    return stored


# ------------------------------------------------------------------ projects
PROJECT_SELECT = """
SELECT p.id, p.title, p.description, p.thumbnail, p.download_count,
       p.created_at, p.updated_at, p.category_id,
       c.name AS category_name,
       f.original_name, f.stored_name, f.extension, f.size_bytes,
       (SELECT group_concat(l.id || ':' || l.name, '|')
          FROM project_languages pl JOIN languages l ON l.id = pl.language_id
         WHERE pl.project_id = p.id) AS language_data
  FROM projects p
  LEFT JOIN categories c ON c.id = p.category_id
  LEFT JOIN files f ON f.project_id = p.id
"""


def project_to_dict(row):
    languages = []
    if row["language_data"]:
        for item in row["language_data"].split("|"):
            lang_id, _, name = item.partition(":")
            languages.append({"id": int(lang_id), "name": name})
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "category_id": row["category_id"],
        "category": row["category_name"] or "Uncategorized",
        "languages": languages,
        "thumbnail": row["thumbnail"],
        "file": {
            "original_name": row["original_name"],
            "extension": row["extension"],
            "size_bytes": row["size_bytes"] or 0,
        },
        "downloads": row["download_count"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_project(project_id):
    row = db.query(PROJECT_SELECT + " WHERE p.id = ?", (project_id,), one=True)
    return project_to_dict(row) if row else None


def search_projects(q="", category_id=None, language_id=None, sort="new", limit=12, offset=0):
    """Return (projects, total_count) for the public site and the admin app."""
    where, params = [], []
    if q:
        like = "%" + q.replace("%", r"\%").replace("_", r"\_") + "%"
        where.append("(p.title LIKE ? ESCAPE '\\' OR p.description LIKE ? ESCAPE '\\')")
        params += [like, like]
    if category_id:
        where.append("p.category_id = ?")
        params.append(category_id)
    if language_id:
        where.append("EXISTS (SELECT 1 FROM project_languages x WHERE x.project_id = p.id AND x.language_id = ?)")
        params.append(language_id)
    clause = (" WHERE " + " AND ".join(where)) if where else ""

    total = db.query("SELECT COUNT(*) AS n FROM projects p" + clause, params, one=True)["n"]
    order = "p.download_count DESC, p.id DESC" if sort == "popular" else "p.created_at DESC, p.id DESC"
    rows = db.query(
        PROJECT_SELECT + clause + " ORDER BY " + order + " LIMIT ? OFFSET ?",
        params + [limit, offset],
    )
    return [project_to_dict(r) for r in rows], total


def resolve_language_ids(raw_ids):
    """Accept '1,2,3' (or a list) and return only ids that really exist."""
    if isinstance(raw_ids, str):
        raw_ids = [x for x in raw_ids.split(",") if x.strip()]
    ids = []
    for item in raw_ids or []:
        try:
            ids.append(int(item))
        except (TypeError, ValueError):
            raise ValidationError("Invalid language selection.")
    if not ids:
        return []
    marks = ",".join("?" * len(ids))
    found = {r["id"] for r in db.query("SELECT id FROM languages WHERE id IN (%s)" % marks, ids)}
    if len(found) != len(set(ids)):
        raise ValidationError("One of the selected languages does not exist.")
    return sorted(found)


def resolve_category_id(raw):
    if raw in (None, "", "0", "null", "None"):
        return None
    try:
        cat_id = int(raw)
    except (TypeError, ValueError):
        raise ValidationError("Invalid category.")
    if db.query("SELECT 1 FROM categories WHERE id = ?", (cat_id,), one=True) is None:
        raise ValidationError("The selected category does not exist.")
    return cat_id


# ------------------------------------------------------------------ formatting
def format_size(num_bytes):
    num = float(num_bytes or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return ("%d %s" % (num, unit)) if unit == "B" else ("%.1f %s" % (num, unit))
        num /= 1024


def format_date(value):
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except (TypeError, ValueError):
        return value or ""
