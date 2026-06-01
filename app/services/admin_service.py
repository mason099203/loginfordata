from datetime import datetime
from typing import Any

from bson import ObjectId

from app.database import get_db
from app.schemas.activity import ActivityOut
from app.schemas.user import UserOut
from app.services.activity_service import _doc_to_activity
from app.services.auth_service import _doc_to_user


def list_users() -> list[UserOut]:
    cursor = get_db().users.find().sort("created_at", -1)
    return [_doc_to_user(doc) for doc in cursor]


def update_user_role(user_id: str, role: str, actor_id: str) -> tuple[bool, str]:
    if role not in ("user", "advanced_user", "admin"):
        return False, "無效的角色"
    if not ObjectId.is_valid(user_id):
        return False, "無效的使用者"
    if user_id == actor_id and role != "admin":
        return False, "無法降低自己的管理員權限"

    db = get_db()
    result = db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": role}},
    )
    if result.matched_count == 0:
        return False, "使用者不存在"
    return True, "權限已更新"


def list_activities_filtered(
    *,
    status: str | None = None,
    keyword: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[ActivityOut]:
    query: dict[str, Any] = {}
    if status == "deleted":
        query["deleted_at"] = {"$ne": None}
    elif status and status in ("draft", "active", "closed"):
        query["status"] = status
        query["deleted_at"] = None
    if keyword:
        query["$or"] = [
            {"title": {"$regex": keyword, "$options": "i"}},
            {"description": {"$regex": keyword, "$options": "i"}},
        ]
    if date_from or date_to:
        time_filter: dict[str, Any] = {}
        if date_from:
            time_filter["$gte"] = date_from
        if date_to:
            time_filter["$lte"] = date_to
        query["start_time"] = time_filter

    cursor = get_db().activities.find(query).sort("start_time", -1)
    return [_doc_to_activity(doc) for doc in cursor]
