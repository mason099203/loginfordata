from datetime import datetime, timezone

import bcrypt
from bson import ObjectId

from app.config import BOOTSTRAP_ADMIN_EMAIL, BOOTSTRAP_ADMIN_PASSWORD
from app.database import get_db
from app.schemas.user import UserOut


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


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
    invite_code: str | None = None,
) -> UserOut:
    invited_by = None
    if invite_code:
        from app.services.invite_code_service import resolve_invite_code_owner

        owner_id = resolve_invite_code_owner(invite_code)
        if not owner_id:
            raise ValueError("邀請碼無效或已停用")
        invited_by = ObjectId(owner_id)

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
        unset_fields = {
            "verification_code": "",
            "verification_code_expires_at": "",
            "blocked_users": "",
        }
        if invited_by:
            updates["invited_by"] = invited_by
        else:
            unset_fields["invited_by"] = ""
        db.users.update_one(
            {"_id": existing["_id"]},
            {
                "$set": updates,
                "$unset": unset_fields,
            },
        )
        existing.update(updates)
        existing.pop("verification_code", None)
        existing.pop("verification_code_expires_at", None)
        existing.pop("blocked_users", None)
        if not invited_by:
            existing.pop("invited_by", None)
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
    if invited_by:
        doc["invited_by"] = invited_by
    result = db.users.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_user(doc)


# --- Email 驗證碼寄信流程已停用 ---
# 備註：Email 驗證僅能由管理員於 /admin/users 代為確認（admin_verify_user_email）。
# 若需恢復，請取消下方註解並還原 app/routers/auth.py 中的驗證路由。
#
# def _generate_verification_code() -> str:
#     return "".join(str(random.randint(0, 9)) for _ in range(6))
#
#
# def issue_verification_code(email: str) -> None:
#     from app.config import VERIFICATION_CODE_EXPIRE_MINUTES
#     from app.services.email_service import send_verification_email
#
#     db = get_db()
#     normalized_email = email.lower().strip()
#     code = _generate_verification_code()
#     expires_at = datetime.now(timezone.utc) + timedelta(minutes=VERIFICATION_CODE_EXPIRE_MINUTES)
#     result = db.users.update_one(
#         {"email": normalized_email, "email_verified": False},
#         {
#             "$set": {
#                 "verification_code": code,
#                 "verification_code_expires_at": expires_at,
#             }
#         },
#     )
#     if result.matched_count == 0:
#         raise ValueError("找不到待驗證的帳號")
#     send_verification_email(normalized_email, code)
#
#
# def verify_email_code(email: str, code: str) -> tuple[bool, str]:
#     ...


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


def get_login_verification_message(email: str) -> str:
    doc = get_user_by_email(email)
    if doc and not doc.get("email_verified", True) and doc.get("invited_by"):
        return "帳號待確認。"
    return "Email 尚未驗證，請填寫邀請碼重新註冊，或聯絡管理員於「使用者管理」頁面代為確認"


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
