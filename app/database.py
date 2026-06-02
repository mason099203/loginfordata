from pymongo import ASCENDING, DESCENDING, MongoClient

from app.config import MONGODB_DB_NAME, MONGODB_URI

_client: MongoClient | None = None
_db = None


def get_client() -> MongoClient:
    global _client
    if _client is None:
        if not MONGODB_URI:
            raise RuntimeError("MONGODB_URI is not set. Copy .env.example to .env and configure it.")
        _client = MongoClient(MONGODB_URI, tz_aware=True)
    return _client


def get_db():
    global _db
    if _db is None:
        _db = get_client()[MONGODB_DB_NAME]
    return _db


def ensure_indexes():
    db = get_db()
    db.users.create_index("email", unique=True)
    db.users.create_index("invite_code", unique=True, sparse=True)
    db.users.create_index([("invited_by", ASCENDING), ("email_verified", ASCENDING)])
    db.activities.create_index([("status", ASCENDING), ("start_time", DESCENDING)])
    db.messages.create_index(
        [("room_type", ASCENDING), ("room_id", ASCENDING), ("created_at", DESCENDING)]
    )
    db.activity_templates.create_index([("created_by", ASCENDING), ("updated_at", DESCENDING)])
    db.registration_logs.create_index([("activity_id", ASCENDING), ("created_at", DESCENDING)])
