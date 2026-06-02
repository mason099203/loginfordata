import re
import secrets
import string

from bson import ObjectId

from app.database import get_db

INVITE_CODE_PATTERN = re.compile(r"^[A-Z0-9]{4,20}$")
_CODE_ALPHABET = string.ascii_uppercase + string.digits
_INVITE_CODE_ROLES = ("advanced_user", "admin")


def _invite_code_owner_query(user_id: str) -> dict:
    return {
        "_id": ObjectId(user_id),
        "is_active": True,
        "role": {"$in": list(_INVITE_CODE_ROLES)},
    }


def normalize_invite_code(code: str) -> str:
    return code.strip().upper()


def generate_invite_code(length: int = 8) -> str:
    db = get_db()
    for _ in range(20):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))
        if not db.users.find_one({"invite_code": code}):
            return code
    raise RuntimeError("無法產生唯一邀請碼")


def get_user_invite_code(user_id: str) -> str | None:
    if not ObjectId.is_valid(user_id):
        return None
    doc = get_db().users.find_one(
        _invite_code_owner_query(user_id),
        {"invite_code": 1},
    )
    if not doc:
        return None
    return doc.get("invite_code")


def ensure_invite_code(user_id: str) -> tuple[bool, str]:
    if not ObjectId.is_valid(user_id):
        return False, "無效的使用者"
    db = get_db()
    doc = db.users.find_one(_invite_code_owner_query(user_id), {"invite_code": 1})
    if not doc:
        return False, "僅高級使用者或管理員可設定邀請碼"
    if doc.get("invite_code"):
        return True, doc["invite_code"]
    code = generate_invite_code()
    db.users.update_one({"_id": doc["_id"]}, {"$set": {"invite_code": code}})
    return True, code


def set_invite_code(user_id: str, code: str) -> tuple[bool, str]:
    if not ObjectId.is_valid(user_id):
        return False, "無效的使用者"
    normalized = normalize_invite_code(code)
    if not INVITE_CODE_PATTERN.match(normalized):
        return False, "邀請碼須為 4～20 字元的英數字"
    db = get_db()
    doc = db.users.find_one(_invite_code_owner_query(user_id))
    if not doc:
        return False, "僅高級使用者或管理員可設定邀請碼"
    conflict = db.users.find_one(
        {"invite_code": normalized, "_id": {"$ne": doc["_id"]}},
    )
    if conflict:
        return False, "此邀請碼已被使用，請換一個"
    db.users.update_one({"_id": doc["_id"]}, {"$set": {"invite_code": normalized}})
    return True, f"邀請碼已更新為 {normalized}"


def regenerate_invite_code(user_id: str) -> tuple[bool, str]:
    if not ObjectId.is_valid(user_id):
        return False, "無效的使用者"
    db = get_db()
    doc = db.users.find_one(_invite_code_owner_query(user_id))
    if not doc:
        return False, "僅高級使用者或管理員可設定邀請碼"
    code = generate_invite_code()
    db.users.update_one({"_id": doc["_id"]}, {"$set": {"invite_code": code}})
    return True, code


def resolve_invite_code_owner(code: str) -> str | None:
    normalized = normalize_invite_code(code)
    if not normalized or not INVITE_CODE_PATTERN.match(normalized):
        return None
    doc = get_db().users.find_one(
        {
            "invite_code": normalized,
            "is_active": True,
            "role": {"$in": list(_INVITE_CODE_ROLES)},
        }
    )
    return str(doc["_id"]) if doc else None


def is_valid_invite_code(code: str) -> bool:
    return resolve_invite_code_owner(code) is not None


def list_pending_invitees(owner_id: str) -> list:
    from app.services.auth_service import _doc_to_user

    if not ObjectId.is_valid(owner_id):
        return []
    cursor = (
        get_db()
        .users.find(
            {
                "invited_by": ObjectId(owner_id),
                "email_verified": False,
                "is_active": True,
            }
        )
        .sort("created_at", -1)
    )
    return [_doc_to_user(doc) for doc in cursor]


def verify_invitee(owner_id: str, target_user_id: str) -> tuple[bool, str]:
    if not ObjectId.is_valid(owner_id) or not ObjectId.is_valid(target_user_id):
        return False, "無效的使用者"
    db = get_db()
    doc = db.users.find_one(
        {"_id": ObjectId(target_user_id), "is_active": True},
        {"display_name": 1, "invited_by": 1, "email_verified": 1},
    )
    if not doc:
        return False, "使用者不存在"
    if doc.get("email_verified", True):
        return False, "此帳號已授權"
    if doc.get("invited_by") != ObjectId(owner_id):
        return False, "此使用者並非使用您的邀請碼註冊"
    db.users.update_one(
        {"_id": ObjectId(target_user_id)},
        {"$set": {"email_verified": True}},
    )
    return True, f"已授權「{doc.get('display_name', '')}」的帳號"


def bulk_verify_invitees(owner_id: str, user_ids: list[str]) -> tuple[int, str]:
    if not ObjectId.is_valid(owner_id):
        return 0, "無效的使用者"
    oids = [ObjectId(uid) for uid in user_ids if ObjectId.is_valid(uid)]
    if not oids:
        return 0, "請至少選擇一位待授權的使用者"
    result = get_db().users.update_many(
        {
            "_id": {"$in": oids},
            "invited_by": ObjectId(owner_id),
            "email_verified": False,
            "is_active": True,
        },
        {"$set": {"email_verified": True}},
    )
    count = result.modified_count
    if count == 0:
        return 0, "所選使用者皆已授權或無法操作"
    return count, f"已批次授權 {count} 位使用者"
