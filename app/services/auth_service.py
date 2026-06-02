from datetime import datetime, timedelta, timezone
import random

from bson import ObjectId
from passlib.context import CryptContext

from app.config import BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_PASSWORD, VERIFICATION_CODE_EXPIRE_MINUTES
from app.database import get_db
from app.schemas.user import UserOut
from app.services.email_service import send_verification_email

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
        email_verified=doc.get("email_verified", True),
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


def create_user(
    email: str,
    password: str,
    display_name: str,
    role: str = "user",
    *,
    email_verified: bool = False,
) -> UserOut:
    db = get_db()
    normalized_email = email.lower().strip()
    now = datetime.now(timezone.utc)
    existing = db.users.find_one({"email": normalized_email})
    if existing:
        if existing.get("is_active", True):
            raise ValueError("此 Email 已被註冊")
        password_hash = hash_password(password)
        updates = {
            "password_hash": password_hash,
            "display_name": display_name.strip(),
            "role": role,
            "created_at": now,
            "is_active": True,
            "email_verified": email_verified,
        }
        db.users.update_one(
            {"_id": existing["_id"]},
            {
                "$set": updates,
                "$unset": {
                    "verification_code": "",
                    "verification_code_expires_at": "",
                    "blocked_users": "",
                },
            },
        )
        existing.update(updates)
        existing.pop("verification_code", None)
        existing.pop("verification_code_expires_at", None)
        existing.pop("blocked_users", None)
        return _doc_to_user(existing)

    doc = {
        "email": normalized_email,
        "password_hash": hash_password(password),
        "display_name": display_name.strip(),
        "role": role,
        "created_at": now,
        "is_active": True,
        "email_verified": email_verified,
    }
    result = db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_user(doc)


def _generate_verification_code() -> str:
    return "".join(str(random.randint(0, 9)) for _ in range(6))


def issue_verification_code(email: str) -> None:
    db = get_db()
    normalized_email = email.lower().strip()
    code = _generate_verification_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=VERIFICATION_CODE_EXPIRE_MINUTES)
    result = db.users.update_one(
        {"email": normalized_email, "email_verified": False},
        {
            "$set": {
                "verification_code": code,
                "verification_code_expires_at": expires_at,
            }
        },
    )
    if result.matched_count == 0:
        raise ValueError("找不到待驗證的帳號")
    send_verification_email(normalized_email, code)


def verify_email_code(email: str, code: str) -> tuple[bool, str]:
    db = get_db()
    normalized_email = email.lower().strip()
    normalized_code = code.strip()
    doc = db.users.find_one({"email": normalized_email})
    if not doc:
        return False, "找不到此帳號"
    if doc.get("email_verified", True):
        return True, "此 Email 已驗證"
    stored = doc.get("verification_code")
    expires_at = doc.get("verification_code_expires_at")
    if not stored or not expires_at:
        return False, "驗證碼已失效，請重新寄送"
    if datetime.now(timezone.utc) > expires_at:
        return False, "驗證碼已過期，請重新寄送"
    if normalized_code != stored:
        return False, "驗證碼錯誤"
    db.users.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {"email_verified": True},
            "$unset": {"verification_code": "", "verification_code_expires_at": ""},
        },
    )
    return True, "Email 驗證成功"


def admin_verify_user_email(user_id: str) -> tuple[bool, str]:
    if not ObjectId.is_valid(user_id):
        return False, "無效的使用者"
    db = get_db()
    result = db.users.update_one(
        {"_id": ObjectId(user_id), "email_verified": False},
        {
            "$set": {"email_verified": True},
            "$unset": {"verification_code": "", "verification_code_expires_at": ""},
        },
    )
    if result.matched_count == 0:
        doc = db.users.find_one({"_id": ObjectId(user_id)})
        if not doc:
            return False, "使用者不存在"
        if doc.get("email_verified", True):
            return False, "此帳號已驗證"
        return False, "無法確認此帳號"
    return True, "已代為確認 Email"


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
        db.users.update_one(
            {"_id": existing["_id"]},
            {"$set": {"role": "admin", "email_verified": True}},
        )
        return
    create_user(email, BOOTSTRAP_ADMIN_PASSWORD, "系統管理員", role="admin", email_verified=True)
