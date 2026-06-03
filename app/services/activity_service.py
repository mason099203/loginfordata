from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from bson import ObjectId

from app.config import APP_TIMEZONE, app_now, db_datetime_to_local, form_datetime_to_utc, utc_now
from app.database import get_db
from app.schemas.activity import ActivityOut, ParticipantOut, PositionOut
from app.services.activity_access_service import (
    generate_unique_access_code,
    normalize_access_code,
)
from app.services.auth_service import get_user_by_id, get_users_by_ids
from app.services.blacklist_service import is_user_blocked
from app.services.registration_log_service import log_registration


def _now() -> datetime:
    return utc_now()


def _not_deleted_filter() -> dict[str, Any]:
    return {"deleted_at": None}


def _is_deleted(doc: dict) -> bool:
    return doc.get("deleted_at") is not None


def _to_local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=APP_TIMEZONE)
    return dt.astimezone(APP_TIMEZONE)


def _is_live(doc: dict, now: datetime | None = None) -> bool:
    now = _to_local(now or app_now())
    start = _to_local(doc["start_time"])
    end = _to_local(doc["end_time"])
    return doc["status"] == "active" and start <= now <= end


def _remaining_info(end_time: datetime, now: datetime | None = None) -> tuple[str, int]:
    now = _to_local(now or app_now())
    end = _to_local(end_time)
    if now >= end:
        return "已結束", 0
    seconds = int((end - now).total_seconds())
    hours, rem = divmod(seconds, 3600)
    minutes, _ = divmod(rem, 60)
    if hours > 0:
        text = f"{hours} 小時 {minutes} 分"
    elif minutes > 0:
        text = f"{minutes} 分鐘"
    else:
        text = "不足 1 分鐘"
    return text, seconds


def _position_to_out(
    pos: dict,
    user_oid: ObjectId | None = None,
    user_names: dict[str, str] | None = None,
) -> PositionOut:
    participant_ids = pos.get("participants", [])
    user_names = user_names or {}
    participants = [
        ParticipantOut(
            user_id=str(uid),
            display_name=user_names.get(str(uid), "未知使用者"),
        )
        for uid in participant_ids
    ]
    return PositionOut(
        id=pos["id"],
        name=pos["name"],
        description=pos.get("description", ""),
        capacity=pos["capacity"],
        participant_count=len(participant_ids),
        is_joined=user_oid in participant_ids if user_oid else False,
        participants=participants,
    )


def _collect_participant_ids(doc: dict) -> list[ObjectId]:
    ids: list[ObjectId] = []
    for pos in doc.get("positions", []):
        ids.extend(pos.get("participants", []))
    return ids


def _doc_to_activity(
    doc: dict,
    user_id: str | None = None,
    *,
    include_access_code: bool = False,
) -> ActivityOut:
    user_oid = ObjectId(user_id) if user_id and ObjectId.is_valid(user_id) else None
    user_names = get_users_by_ids(_collect_participant_ids(doc))
    positions = [_position_to_out(p, user_oid, user_names) for p in doc.get("positions", [])]
    total_capacity = sum(p.capacity for p in positions)
    total_participants = sum(p.participant_count for p in positions)
    remaining_text, remaining_seconds = _remaining_info(doc["end_time"])
    deleted_at_raw = doc.get("deleted_at")
    visibility = doc.get("visibility", "public")
    access_code = doc.get("access_code") if include_access_code else None
    return ActivityOut(
        id=str(doc["_id"]),
        title=doc["title"],
        description=doc.get("description", ""),
        image_url=doc.get("image_url"),
        start_time=db_datetime_to_local(doc["start_time"]),
        end_time=db_datetime_to_local(doc["end_time"]),
        status=doc["status"],
        positions=positions,
        created_by=str(doc["created_by"]),
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
        is_live=_is_live(doc),
        total_capacity=total_capacity,
        total_participants=total_participants,
        remaining_text=remaining_text,
        remaining_seconds=remaining_seconds,
        deleted_at=db_datetime_to_local(deleted_at_raw) if deleted_at_raw else None,
        visibility=visibility,
        access_code=access_code,
    )


def list_active_activities(user_id: str | None = None) -> list[ActivityOut]:
    now = app_now()
    cursor = (
        get_db()
        .activities.find(
            {
                "status": "active",
                "visibility": {"$ne": "private"},
                **_not_deleted_filter(),
            }
        )
        .sort("start_time", 1)
    )
    results = []
    for doc in cursor:
        if _is_live(doc, now):
            results.append(_doc_to_activity(doc, user_id))
    return results


def get_activity(
    activity_id: str,
    user_id: str | None = None,
    *,
    include_deleted: bool = False,
    include_access_code: bool = False,
) -> ActivityOut | None:
    if not ObjectId.is_valid(activity_id):
        return None
    doc = get_db().activities.find_one({"_id": ObjectId(activity_id)})
    if not doc:
        return None
    if not include_deleted and _is_deleted(doc):
        return None
    show_code = include_access_code
    if not show_code and user_id and str(doc.get("created_by")) == user_id:
        show_code = True
    return _doc_to_activity(doc, user_id, include_access_code=show_code)


def list_my_activities(user_id: str) -> list[ActivityOut]:
    if not ObjectId.is_valid(user_id):
        return []
    cursor = (
        get_db()
        .activities.find({"created_by": ObjectId(user_id), **_not_deleted_filter()})
        .sort("updated_at", -1)
    )
    return [_doc_to_activity(doc, user_id) for doc in cursor]


def _draft_placeholder_times() -> tuple[datetime, datetime]:
    start = db_datetime_to_local(app_now())
    return start, start + timedelta(days=1)


def create_activity(
    user_id: str,
    title: str,
    description: str,
    *,
    image_url: str | None = None,
    positions: list[dict[str, Any]] | None = None,
) -> ActivityOut:
    now = _now()
    start_time, end_time = _draft_placeholder_times()
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
        "start_time": form_datetime_to_utc(start_time),
        "end_time": form_datetime_to_utc(end_time),
        "status": "draft",
        "positions": activity_positions,
        "created_by": ObjectId(user_id),
        "created_at": now,
        "updated_at": now,
        "deleted_at": None,
        "visibility": "public",
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
    set_image_url: bool = False,
    visibility: str | None = None,
) -> ActivityOut | None:
    if not ObjectId.is_valid(activity_id):
        return None
    db = get_db()
    doc = db.activities.find_one(
        {"_id": ObjectId(activity_id), "created_by": ObjectId(user_id), **_not_deleted_filter()}
    )
    if not doc:
        return None

    update: dict[str, Any] = {"updated_at": _now()}
    if title is not None:
        update["title"] = title.strip()
    if description is not None:
        update["description"] = description.strip()
    if start_time is not None:
        update["start_time"] = form_datetime_to_utc(start_time)
    if end_time is not None:
        update["end_time"] = form_datetime_to_utc(end_time)
    if set_image_url:
        update["image_url"] = image_url
    elif image_url is not None:
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

    if visibility is not None:
        if visibility not in ("public", "private"):
            return None
        update["visibility"] = visibility
        if visibility == "private" and not doc.get("access_code"):
            update["access_code"] = generate_unique_access_code()

    update_op: dict[str, Any] = {"$set": update}
    if visibility == "public":
        update_op["$unset"] = {"access_code": ""}

    db.activities.update_one({"_id": doc["_id"]}, update_op)
    updated = db.activities.find_one({"_id": doc["_id"]})
    return _doc_to_activity(updated, user_id)


def set_activity_status(
    activity_id: str,
    user_id: str,
    status: str,
    duration_hours: int | None = None,
    start_time: datetime | None = None,
) -> ActivityOut | None:
    if status not in ("draft", "active", "closed"):
        return None
    if not ObjectId.is_valid(activity_id):
        return None
    if status == "active":
        return activate_activity(activity_id, user_id, duration_hours or 3, start_time=start_time)
    db = get_db()
    result = db.activities.update_one(
        {"_id": ObjectId(activity_id), "created_by": ObjectId(user_id), **_not_deleted_filter()},
        {"$set": {"status": status, "updated_at": _now()}},
    )
    if result.matched_count == 0:
        return None
    doc = db.activities.find_one({"_id": ObjectId(activity_id)})
    return _doc_to_activity(doc, user_id)


def delete_activity(activity_id: str, user_id: str) -> bool:
    if not ObjectId.is_valid(activity_id) or not ObjectId.is_valid(user_id):
        return False
    db = get_db()
    result = db.activities.update_one(
        {"_id": ObjectId(activity_id), "created_by": ObjectId(user_id), **_not_deleted_filter()},
        {"$set": {"deleted_at": _now(), "updated_at": _now()}},
    )
    return result.matched_count > 0


def activate_activity(
    activity_id: str,
    user_id: str,
    duration_hours: int,
    *,
    start_time: datetime | None = None,
) -> ActivityOut | None:
    allowed = {1, 2, 3, 6, 12, 24}
    if duration_hours not in allowed:
        return None
    if not ObjectId.is_valid(activity_id):
        return None
    start_utc = form_datetime_to_utc(start_time) if start_time is not None else utc_now()
    end_utc = start_utc + timedelta(hours=duration_hours)
    db = get_db()
    result = db.activities.update_one(
        {"_id": ObjectId(activity_id), "created_by": ObjectId(user_id), **_not_deleted_filter()},
        {
            "$set": {
                "status": "active",
                "start_time": start_utc,
                "end_time": end_utc,
                "updated_at": start_utc,
            }
        },
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
    if _is_deleted(doc):
        return False, "活動不存在"
    if is_user_blocked(str(doc["created_by"]), user_id):
        return False, "您已被活動主辦方列入黑名單，無法報名"
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
    actor = get_user_by_id(user_id)
    log_registration(
        activity_id,
        position_id,
        target["name"],
        user_id,
        actor.display_name if actor else "未知使用者",
        "join",
    )
    return True, "報名成功"


def leave_position(activity_id: str, position_id: str, user_id: str) -> tuple[bool, str]:
    if not ObjectId.is_valid(activity_id) or not ObjectId.is_valid(user_id):
        return False, "無效的請求"

    db = get_db()
    doc = db.activities.find_one({"_id": ObjectId(activity_id)})
    if not doc:
        return False, "活動不存在"
    if _is_deleted(doc):
        return False, "活動不存在"

    user_oid = ObjectId(user_id)
    target = next((p for p in doc.get("positions", []) if p["id"] == position_id), None)
    if not target or user_oid not in target.get("participants", []):
        return False, "您未報名此位置"

    db.activities.update_one(
        {"_id": doc["_id"], "positions.id": position_id},
        {"$pull": {"positions.$.participants": user_oid}, "$set": {"updated_at": _now()}},
    )
    actor = get_user_by_id(user_id)
    log_registration(
        activity_id,
        position_id,
        target["name"],
        user_id,
        actor.display_name if actor else "未知使用者",
        "leave",
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
    if not doc or _is_deleted(doc):
        return False
    if str(doc["created_by"]) == user_id and user_role in ("advanced_user", "admin"):
        return True
    return user_joined_activity(activity_id, user_id)


def _get_activity_doc(activity_id: str) -> dict | None:
    if not ObjectId.is_valid(activity_id):
        return None
    return get_db().activities.find_one({"_id": ObjectId(activity_id)})


def is_private_activity(doc: dict) -> bool:
    return doc.get("visibility") == "private"


def verify_activity_access_code(activity_id: str, code: str) -> bool:
    doc = _get_activity_doc(activity_id)
    if not doc or _is_deleted(doc):
        return False
    if not is_private_activity(doc):
        return True
    stored = doc.get("access_code")
    if not stored:
        return False
    return normalize_access_code(code) == stored


def find_activity_id_by_access_code(code: str) -> str | None:
    normalized = normalize_access_code(code)
    if not normalized:
        return None
    doc = get_db().activities.find_one(
        {
            "access_code": normalized,
            "visibility": "private",
            **_not_deleted_filter(),
        }
    )
    return str(doc["_id"]) if doc else None


def can_view_activity(
    activity_id: str,
    user_id: str,
    user_role: str,
    *,
    has_access_cookie: bool = False,
) -> bool:
    doc = _get_activity_doc(activity_id)
    if not doc or _is_deleted(doc):
        return False
    if not is_private_activity(doc):
        return True
    if user_role == "admin":
        return True
    if str(doc["created_by"]) == user_id:
        return True
    if user_joined_activity(activity_id, user_id):
        return True
    return has_access_cookie


def regenerate_activity_access_code(activity_id: str, user_id: str) -> tuple[bool, str]:
    if not ObjectId.is_valid(activity_id):
        return False, "無效的活動"
    db = get_db()
    doc = db.activities.find_one(
        {"_id": ObjectId(activity_id), "created_by": ObjectId(user_id), **_not_deleted_filter()}
    )
    if not doc:
        return False, "無權操作此活動"
    if not is_private_activity(doc):
        return False, "僅非公開活動可重設代碼"
    code = generate_unique_access_code()
    db.activities.update_one(
        {"_id": doc["_id"]},
        {"$set": {"access_code": code, "updated_at": _now()}},
    )
    return True, code
