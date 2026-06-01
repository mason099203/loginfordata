from bson import ObjectId

from app.database import get_db
from app.schemas.user import UserOut
from app.services.auth_service import _doc_to_user, get_user_by_email


def _get_blocked_ids(owner_id: str) -> list[ObjectId]:
    if not ObjectId.is_valid(owner_id):
        return []
    doc = get_db().users.find_one({"_id": ObjectId(owner_id)}, {"blocked_users": 1})
    return doc.get("blocked_users", []) if doc else []


def is_user_blocked(owner_id: str, user_id: str) -> bool:
    if not ObjectId.is_valid(owner_id) or not ObjectId.is_valid(user_id):
        return False
    if owner_id == user_id:
        return False
    return ObjectId(user_id) in _get_blocked_ids(owner_id)


def list_blocked_users(owner_id: str) -> list[UserOut]:
    blocked_ids = _get_blocked_ids(owner_id)
    if not blocked_ids:
        return []
    cursor = get_db().users.find({"_id": {"$in": blocked_ids}}).sort("display_name", 1)
    return [_doc_to_user(doc) for doc in cursor]


def add_to_blacklist(owner_id: str, email: str) -> tuple[bool, str]:
    if not ObjectId.is_valid(owner_id):
        return False, "無效的請求"
    normalized = email.lower().strip()
    if not normalized:
        return False, "請輸入 Email"

    target = get_user_by_email(normalized)
    if not target:
        return False, "找不到此 Email 的使用者"

    target_id = target["_id"]
    if str(target_id) == owner_id:
        return False, "無法將自己加入黑名單"

    if target.get("role") == "admin":
        return False, "無法將管理員加入黑名單"

    result = get_db().users.update_one(
        {"_id": ObjectId(owner_id)},
        {"$addToSet": {"blocked_users": target_id}},
    )
    if result.matched_count == 0:
        return False, "操作失敗"
    return True, f"已將 {target['display_name']} 加入黑名單"


def remove_from_blacklist(owner_id: str, target_user_id: str) -> tuple[bool, str]:
    if not ObjectId.is_valid(owner_id) or not ObjectId.is_valid(target_user_id):
        return False, "無效的請求"
    result = get_db().users.update_one(
        {"_id": ObjectId(owner_id)},
        {"$pull": {"blocked_users": ObjectId(target_user_id)}},
    )
    if result.modified_count == 0:
        return False, "使用者不在黑名單中"
    return True, "已移出黑名單"
