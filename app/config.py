import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB_NAME = os.getenv("MONGODB_DB_NAME", "activity_app")
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")
BOOTSTRAP_ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
BOOTSTRAP_ADMIN_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "change-me")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "app/static/uploads"))
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "2"))

if not UPLOAD_DIR.is_absolute():
    UPLOAD_DIR = BASE_DIR / UPLOAD_DIR

SESSION_COOKIE_NAME = "session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

ROLES = ("user", "advanced_user", "admin")
ACTIVITY_STATUSES = ("draft", "active", "closed")
