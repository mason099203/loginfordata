from bson import ObjectId

from app.config import db_datetime_to_local, utc_now
from app.database import get_db
from app.schemas.registration_log import RegistrationLogOut

ACTION_LABELS = {"join": "報名", "leave": "取消報名"}


def _doc_to_log(doc: dict) -> RegistrationLogOut:
    action = doc["action"]
    return RegistrationLogOut(
        id=str(doc["_id"]),
        activity_id=str(doc["activity_id"]),
        position_id=doc["position_id"],
        position_name=doc["position_name"],
        user_id=str(doc["user_id"]),
        user_name=doc["user_name"],
        action=action,
        action_label=ACTION_LABELS.get(action, action),
        created_at=db_datetime_to_local(doc["created_at"]),
    )


def log_registration(
    activity_id: str,
    position_id: str,
    position_name: str,
    user_id: str,
    user_name: str,
    action: str,
) -> None:
    if action not in ("join", "leave"):
        return
    if not ObjectId.is_valid(activity_id) or not ObjectId.is_valid(user_id):
        return
    get_db().registration_logs.insert_one(
        {
            "activity_id": ObjectId(activity_id),
            "position_id": position_id,
            "position_name": position_name,
            "user_id": ObjectId(user_id),
            "user_name": user_name,
            "action": action,
            "created_at": utc_now(),
        }
    )


def list_registration_logs(activity_id: str, limit: int = 100) -> list[RegistrationLogOut]:
    if not ObjectId.is_valid(activity_id):
        return []
    cursor = (
        get_db()
        .registration_logs.find({"activity_id": ObjectId(activity_id)})
        .sort("created_at", -1)
        .limit(limit)
    )
    return [_doc_to_log(doc) for doc in cursor]
