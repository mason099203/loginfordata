from datetime import datetime
from typing import Any
from urllib.parse import quote

from bson import ObjectId

from app.database import get_db
from app.schemas.activity import ActivityOut
from app.schemas.user import UserOut
from app.services.activity_service import _doc_to_activity
from app.services.auth_service import _doc_to_user, admin_verify_user_email

ROLE_LABELS = {
    "user": "一般使用者",
    "advanced_user": "高級使用者",
    "admin": "管理員",
}


def list_users() -> list[UserOut]:
    cursor = get_db().users.find({"is_active": True}).sort("created_at", -1)
    return [_doc_to_user(doc) for doc in cursor]


def update_user_role(user_id: str, role: str, actor_id: str) -> tuple[bool, str]:
    if role not in ROLE_LABELS:
        return False, "無效的角色"
    if not ObjectId.is_valid(user_id):
        return False, "無效的使用者"
    if user_id == actor_id and role != "admin":
        return False, "無法降低自己的管理員權限"

    db = get_db()
    doc = db.users.find_one({"_id": ObjectId(user_id), "is_active": True})
    if not doc:
        return False, "使用者不存在"

    old_role = doc.get("role")
    display_name = doc.get("display_name", "")
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"role": role}},
    )
    if role == "admin" and old_role != "admin":
        return True, f"已將「{display_name}」設為管理員"
    if old_role == role:
        return True, f"「{display_name}」已是{ROLE_LABELS[role]}"
    return True, f"已將「{display_name}」的角色更新為{ROLE_LABELS[role]}"


def delete_user(user_id: str, actor_id: str) -> tuple[bool, str]:
    if not ObjectId.is_valid(user_id):
        return False, "無效的使用者"
    if user_id == actor_id:
        return False, "無法刪除自己的帳號"

    db = get_db()
    doc = db.users.find_one({"_id": ObjectId(user_id), "is_active": True})
    if not doc:
        return False, "使用者不存在或已刪除"

    if doc.get("role") == "admin":
        admin_count = db.users.count_documents({"role": "admin", "is_active": True})
        if admin_count <= 1:
            return False, "無法刪除最後一位管理員"

    display_name = doc.get("display_name", "")
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"is_active": False}},
    )
    return True, f"已刪除使用者「{display_name}」"


def verify_user_email(user_id: str) -> tuple[bool, str]:
    return admin_verify_user_email(user_id)


def bulk_verify_user_emails(user_ids: list[str], actor_id: str) -> tuple[int, str]:
    db = get_db()
    oids = [
        ObjectId(uid)
        for uid in user_ids
        if ObjectId.is_valid(uid) and uid != actor_id
    ]
    if not oids:
        return 0, "請至少選擇一位待驗證的使用者"
    result = db.users.update_many(
        {"_id": {"$in": oids}, "email_verified": False, "is_active": True},
        {
            "$set": {"email_verified": True},
            "$unset": {"verification_code": "", "verification_code_expires_at": ""},
        },
    )
    count = result.modified_count
    if count == 0:
        return 0, "所選使用者皆已驗證或無法確認"
    return count, f"已批次確認 {count} 位使用者的 Email"


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
