import os
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

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
APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Taipei"))

if not UPLOAD_DIR.is_absolute():
    UPLOAD_DIR = BASE_DIR / UPLOAD_DIR


def app_now() -> datetime:
    """Current time in app timezone (aware)."""
    return datetime.now(APP_TIMEZONE)


def form_datetime_to_utc(dt: datetime) -> datetime:
    """datetime-local form values are naive app timezone; store as UTC."""
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=APP_TIMEZONE).astimezone(timezone.utc)


def db_datetime_to_local(dt: datetime) -> datetime:
    """Convert MongoDB datetime to naive app timezone for templates."""
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(APP_TIMEZONE).replace(tzinfo=None)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

SESSION_COOKIE_NAME = "session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7  # 7 days

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "").replace(" ", "")
SMTP_FROM = os.getenv("SMTP_FROM", "") or (
    f"活動管理系統 <{SMTP_USER}>" if SMTP_USER else "活動管理系統 <noreply@example.com>"
)
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
VERIFICATION_CODE_EXPIRE_MINUTES = int(os.getenv("VERIFICATION_CODE_EXPIRE_MINUTES", "15"))

ROLES = ("user", "advanced_user", "admin")
ACTIVITY_STATUSES = ("draft", "active", "closed")
