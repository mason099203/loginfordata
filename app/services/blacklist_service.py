import re

from bson import ObjectId

from app.database import get_db
from app.schemas.user import UserOut
from app.services.auth_service import _doc_to_user


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


def add_to_blacklist(owner_id: str, display_name: str) -> tuple[bool, str]:
    if not ObjectId.is_valid(owner_id):
        return False, "無效的請求"
    name = display_name.strip()
    if not name:
        return False, "請輸入使用者名稱"

    db = get_db()
    matches = list(
        db.users.find(
            {
                "display_name": {"$regex": f"^{re.escape(name)}$", "$options": "i"},
                "is_active": True,
            }
        )
    )
    if not matches:
        return False, "找不到此名稱的使用者"
    if len(matches) > 1:
        return False, "有多位使用者使用相同名稱，無法自動加入"

    target = matches[0]
    target_id = target["_id"]
    if str(target_id) == owner_id:
        return False, "無法將自己加入黑名單"

    if target.get("role") == "admin":
        return False, "無法將管理員加入黑名單"

    result = db.users.update_one(
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
