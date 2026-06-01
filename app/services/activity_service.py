from datetime import datetime
from typing import Any
from uuid import uuid4

from bson import ObjectId

from app.config import app_now
from app.database import get_db
from app.schemas.activity import ActivityOut, PositionOut


def _now() -> datetime:
    return app_now()


def _is_live(doc: dict, now: datetime | None = None) -> bool:
    now = now or _now()
    start = doc["start_time"]
    end = doc["end_time"]
    if hasattr(start, "tzinfo") and start.tzinfo:
        start = start.replace(tzinfo=None)
    if hasattr(end, "tzinfo") and end.tzinfo:
        end = end.replace(tzinfo=None)
    return doc["status"] == "active" and start <= now <= end


def _position_to_out(pos: dict, user_oid: ObjectId | None = None) -> PositionOut:
    participants = pos.get("participants", [])
    return PositionOut(
        id=pos["id"],
        name=pos["name"],
        description=pos.get("description", ""),
        capacity=pos["capacity"],
        participant_count=len(participants),
        is_joined=user_oid in participants if user_oid else False,
    )


def _doc_to_activity(doc: dict, user_id: str | None = None) -> ActivityOut:
    user_oid = ObjectId(user_id) if user_id and ObjectId.is_valid(user_id) else None
    positions = [_position_to_out(p, user_oid) for p in doc.get("positions", [])]
    return ActivityOut(
        id=str(doc["_id"]),
        title=doc["title"],
        description=doc.get("description", ""),
        image_url=doc.get("image_url"),
        start_time=doc["start_time"],
        end_time=doc["end_time"],
        status=doc["status"],
        positions=positions,
        created_by=str(doc["created_by"]),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        is_live=_is_live(doc),
    )


def list_active_activities(user_id: str | None = None) -> list[ActivityOut]:
    now = _now()
    cursor = get_db().activities.find({"status": "active"}).sort("start_time", 1)
    results = []
    for doc in cursor:
        if _is_live(doc, now):
            results.append(_doc_to_activity(doc, user_id))
    return results


def get_activity(activity_id: str, user_id: str | None = None) -> ActivityOut | None:
    if not ObjectId.is_valid(activity_id):
        return None
    doc = get_db().activities.find_one({"_id": ObjectId(activity_id)})
    return _doc_to_activity(doc, user_id) if doc else None


def list_my_activities(user_id: str) -> list[ActivityOut]:
    if not ObjectId.is_valid(user_id):
        return []
    cursor = (
        get_db()
        .activities.find({"created_by": ObjectId(user_id)})
        .sort("updated_at", -1)
    )
    return [_doc_to_activity(doc, user_id) for doc in cursor]


def create_activity(
    user_id: str,
    title: str,
    description: str,
    start_time: datetime,
    end_time: datetime,
    *,
    image_url: str | None = None,
    positions: list[dict[str, Any]] | None = None,
) -> ActivityOut:
    now = _now()
    activity_positions = []
    if positions:
        for pos in positions:
            activity_positions.append(
                {
                    "id": str(uuid4()),
                    "name": pos["name"].strip(),
                    "description": pos.get("description", "").strip(),
                    "capacity": int(pos["capacity"]),
                    "participants": [],
                }
            )
    doc = {
        "title": title.strip(),
        "description": description.strip(),
        "image_url": image_url,
        "start_time": start_time,
        "end_time": end_time,
        "status": "draft",
        "positions": activity_positions,
        "created_by": ObjectId(user_id),
        "created_at": now,
        "updated_at": now,
    }
    result = get_db().activities.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_activity(doc, user_id)


def update_activity(
    activity_id: str,
    user_id: str,
    *,
    title: str | None = None,
    description: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
    image_url: str | None = None,
    positions: list[dict[str, Any]] | None = None,
) -> ActivityOut | None:
    if not ObjectId.is_valid(activity_id):
        return None
    db = get_db()
    doc = db.activities.find_one({"_id": ObjectId(activity_id), "created_by": ObjectId(user_id)})
    if not doc:
        return None

    update: dict[str, Any] = {"updated_at": _now()}
    if title is not None:
        update["title"] = title.strip()
    if description is not None:
        update["description"] = description.strip()
    if start_time is not None:
        update["start_time"] = start_time
    if end_time is not None:
        update["end_time"] = end_time
    if image_url is not None:
        update["image_url"] = image_url

    if positions is not None:
        existing = {p["id"]: p for p in doc.get("positions", [])}
        new_positions = []
        for pos in positions:
            pid = pos.get("id") or str(uuid4())
            old = existing.get(pid, {})
            new_positions.append(
                {
                    "id": pid,
                    "name": pos["name"].strip(),
                    "description": pos.get("description", "").strip(),
                    "capacity": int(pos["capacity"]),
                    "participants": old.get("participants", []),
                }
            )
        update["positions"] = new_positions

    db.activities.update_one({"_id": doc["_id"]}, {"$set": update})
    updated = db.activities.find_one({"_id": doc["_id"]})
    return _doc_to_activity(updated, user_id)


def set_activity_status(activity_id: str, user_id: str, status: str) -> ActivityOut | None:
    if status not in ("draft", "active", "closed"):
        return None
    if not ObjectId.is_valid(activity_id):
        return None
    db = get_db()
    result = db.activities.update_one(
        {"_id": ObjectId(activity_id), "created_by": ObjectId(user_id)},
        {"$set": {"status": status, "updated_at": _now()}},
    )
    if result.matched_count == 0:
        return None
    doc = db.activities.find_one({"_id": ObjectId(activity_id)})
    return _doc_to_activity(doc, user_id)


def join_position(activity_id: str, position_id: str, user_id: str) -> tuple[bool, str]:
    if not ObjectId.is_valid(activity_id) or not ObjectId.is_valid(user_id):
        return False, "無效的請求"

    db = get_db()
    doc = db.activities.find_one({"_id": ObjectId(activity_id)})
    if not doc:
        return False, "活動不存在"
    if not _is_live(doc):
        return False, "活動未在進行中，無法報名"

    user_oid = ObjectId(user_id)
    for pos in doc.get("positions", []):
        if user_oid in pos.get("participants", []):
            return False, "您已在其他位置報名此活動"

    target = None
    for pos in doc.get("positions", []):
        if pos["id"] == position_id:
            target = pos
            break
    if not target:
        return False, "找不到指定位置"

    participants = target.get("participants", [])
    if user_oid in participants:
        return False, "您已報名此位置"
    if len(participants) >= target["capacity"]:
        return False, "此位置已額滿"

    db.activities.update_one(
        {"_id": doc["_id"], "positions.id": position_id},
        {"$push": {"positions.$.participants": user_oid}, "$set": {"updated_at": _now()}},
    )
    return True, "報名成功"


def leave_position(activity_id: str, position_id: str, user_id: str) -> tuple[bool, str]:
    if not ObjectId.is_valid(activity_id) or not ObjectId.is_valid(user_id):
        return False, "無效的請求"

    db = get_db()
    doc = db.activities.find_one({"_id": ObjectId(activity_id)})
    if not doc:
        return False, "活動不存在"

    user_oid = ObjectId(user_id)
    target = next((p for p in doc.get("positions", []) if p["id"] == position_id), None)
    if not target or user_oid not in target.get("participants", []):
        return False, "您未報名此位置"

    db.activities.update_one(
        {"_id": doc["_id"], "positions.id": position_id},
        {"$pull": {"positions.$.participants": user_oid}, "$set": {"updated_at": _now()}},
    )
    return True, "已取消報名"


def user_joined_activity(activity_id: str, user_id: str) -> bool:
    if not ObjectId.is_valid(activity_id) or not ObjectId.is_valid(user_id):
        return False
    doc = get_db().activities.find_one({"_id": ObjectId(activity_id)})
    if not doc:
        return False
    user_oid = ObjectId(user_id)
    for pos in doc.get("positions", []):
        if user_oid in pos.get("participants", []):
            return True
    return False


def can_access_activity_chat(activity_id: str, user_id: str, user_role: str) -> bool:
    if user_role == "admin":
        return True
    doc = get_db().activities.find_one({"_id": ObjectId(activity_id)}) if ObjectId.is_valid(activity_id) else None
    if not doc:
        return False
    if str(doc["created_by"]) == user_id and user_role == "advanced_user":
        return True
    return user_joined_activity(activity_id, user_id)
