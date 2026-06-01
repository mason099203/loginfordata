from datetime import datetime, timezone

from bson import ObjectId
from passlib.context import CryptContext

from app.config import BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_PASSWORD
from app.database import get_db
from app.schemas.user import UserOut

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _doc_to_user(doc: dict) -> UserOut:
    return UserOut(
        id=str(doc["_id"]),
        email=doc["email"],
        display_name=doc["display_name"],
        role=doc["role"],
        created_at=doc["created_at"],
        is_active=doc.get("is_active", True),
    )


def get_user_by_id(user_id: str) -> UserOut | None:
    if not ObjectId.is_valid(user_id):
        return None
    doc = get_db().users.find_one({"_id": ObjectId(user_id), "is_active": True})
    return _doc_to_user(doc) if doc else None


def get_user_by_email(email: str) -> dict | None:
    return get_db().users.find_one({"email": email.lower().strip()})


def get_users_by_ids(user_ids: list) -> dict[str, str]:
    oids = [ObjectId(uid) for uid in user_ids if ObjectId.is_valid(str(uid))]
    if not oids:
        return {}
    cursor = get_db().users.find({"_id": {"$in": oids}}, {"display_name": 1})
    return {str(doc["_id"]): doc["display_name"] for doc in cursor}


def create_user(email: str, password: str, display_name: str, role: str = "user") -> UserOut:
    db = get_db()
    normalized_email = email.lower().strip()
    if db.users.find_one({"email": normalized_email}):
        raise ValueError("此 Email 已被註冊")

    now = datetime.now(timezone.utc)
    doc = {
        "email": normalized_email,
        "password_hash": hash_password(password),
        "display_name": display_name.strip(),
        "role": role,
        "created_at": now,
        "is_active": True,
    }
    result = db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_user(doc)


def authenticate_user(email: str, password: str) -> UserOut | None:
    doc = get_user_by_email(email)
    if not doc or not doc.get("is_active", True):
        return None
    if not verify_password(password, doc["password_hash"]):
        return None
    return _doc_to_user(doc)


def bootstrap_admin():
    db = get_db()
    if db.users.find_one({"role": "admin"}):
        return
    email = BOOTSTRAP_ADMIN_EMAIL.lower().strip()
    existing = db.users.find_one({"email": email})
    if existing:
        db.users.update_one({"_id": existing["_id"]}, {"$set": {"role": "admin"}})
        return
    create_user(email, BOOTSTRAP_ADMIN_PASSWORD, "系統管理員", role="admin")
