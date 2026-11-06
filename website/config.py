"""
config.py - All settings for the PREMEYFILES website.

Sensitive values (secret key, admin password) are read from environment
variables or from the .env file. Nothing secret is written in the code.
"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent      # .../PREMEYFILES/website
ROOT_DIR = BASE_DIR.parent                      # .../PREMEYFILES

# Load the .env file (if it exists). Real environment variables win over it.
load_dotenv(ROOT_DIR / ".env")
load_dotenv(BASE_DIR / ".env")


def _path_from_env(name, default):
    value = os.environ.get(name, "").strip()
    return Path(value).expanduser().resolve() if value else default


def _int_from_env(name, default):
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


# ---------------------------------------------------------------- storage
DATABASE_PATH = _path_from_env("DATABASE_PATH", ROOT_DIR / "database" / "premeyfiles.db")
UPLOAD_DIR = _path_from_env("UPLOAD_DIR", BASE_DIR / "uploads")
FILES_DIR = UPLOAD_DIR / "files"            # source-code files (never served directly)
THUMBS_DIR = UPLOAD_DIR / "thumbnails"      # preview images


# ---------------------------------------------------------------- secret key
def get_secret_key():
    """Use SECRET_KEY from the environment. If it is missing, create a random
    one once and keep it in database/.secret_key so sessions survive restarts."""
    key = os.environ.get("SECRET_KEY", "").strip()
    if key:
        return key
    key_file = DATABASE_PATH.parent / ".secret_key"
    key_file.parent.mkdir(parents=True, exist_ok=True)
    if key_file.exists():
        return key_file.read_text().strip()
    key = secrets.token_hex(32)
    key_file.write_text(key)
    print("[PREMEYFILES] No SECRET_KEY set - generated one and saved it to", key_file)
    print("[PREMEYFILES] For production, set SECRET_KEY in your environment instead.")
    return key


SECRET_KEY = get_secret_key()

# ---------------------------------------------------------------- uploads
# Hard ceiling for any request (the admin can choose a lower limit in Settings).
HARD_MAX_UPLOAD_MB = _int_from_env("MAX_UPLOAD_MB_LIMIT", 512)
DEFAULT_MAX_UPLOAD_MB = min(100, HARD_MAX_UPLOAD_MB)
MAX_THUMBNAIL_MB = 5

DEFAULT_ALLOWED_EXTENSIONS = (
    "zip,rar,7z,py,html,css,js,php,java,cpp,c,txt,pdf,json,sql"
)

# These are never accepted, even if an administrator adds them in Settings.
BLOCKED_EXTENSIONS = {
    "exe", "dll", "msi", "com", "scr", "bat", "cmd", "vbs", "ps1", "lnk",
}

THUMBNAIL_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

# ---------------------------------------------------------------- admin
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
TOKEN_HOURS = _int_from_env("TOKEN_HOURS", 12)
MIN_PASSWORD_LENGTH = 8

# ---------------------------------------------------------------- web server
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = _int_from_env("PORT", 5000)
# Set to 1 when the site is behind a proxy / hosting platform that uses HTTPS.
TRUST_PROXY = os.environ.get("TRUST_PROXY", "0") == "1"
# Set to 1 once the site is served over HTTPS so cookies are marked Secure.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"

PROJECTS_PER_PAGE = 12
