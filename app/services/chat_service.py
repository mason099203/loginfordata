from datetime import datetime, timezone

from bson import ObjectId

from app.database import get_db
from app.schemas.chat import MessageOut


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _doc_to_message(doc: dict) -> MessageOut:
    return MessageOut(
        id=str(doc["_id"]),
        room_type=doc["room_type"],
        room_id=str(doc["room_id"]) if doc.get("room_id") else None,
        sender_id=str(doc["sender_id"]),
        sender_name=doc["sender_name"],
        content=doc["content"],
        created_at=doc["created_at"],
    )


def save_message(
    room_type: str,
    room_id: str | None,
    sender_id: str,
    sender_name: str,
    content: str,
) -> MessageOut:
    doc = {
        "room_type": room_type,
        "room_id": ObjectId(room_id) if room_id and ObjectId.is_valid(room_id) else None,
        "sender_id": ObjectId(sender_id),
        "sender_name": sender_name,
        "content": content.strip(),
        "created_at": _now(),
    }
    result = get_db().messages.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_message(doc)


def get_recent_messages(room_type: str, room_id: str | None = None, limit: int = 50) -> list[MessageOut]:
    query: dict = {"room_type": room_type}
    if room_type == "activity" and room_id and ObjectId.is_valid(room_id):
        query["room_id"] = ObjectId(room_id)
    elif room_type == "global":
        query["room_id"] = None

    cursor = (
        get_db()
        .messages.find(query)
        .sort("created_at", -1)
        .limit(limit)
    )
    messages = [_doc_to_message(doc) for doc in cursor]
    messages.reverse()
    return messages
