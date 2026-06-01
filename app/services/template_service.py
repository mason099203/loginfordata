from datetime import datetime
from uuid import uuid4

from bson import ObjectId

from app.database import get_db
from app.schemas.template import TemplateFormData, TemplateOut, TemplatePositionOut


def _now() -> datetime:
    return datetime.now()


def _doc_to_template(doc: dict) -> TemplateOut:
    positions = [
        TemplatePositionOut(
            name=p["name"],
            description=p.get("description", ""),
            capacity=p["capacity"],
        )
        for p in doc.get("positions", [])
    ]
    return TemplateOut(
        id=str(doc["_id"]),
        name=doc["name"],
        title=doc["title"],
        description=doc.get("description", ""),
        image_url=doc.get("image_url"),
        positions=positions,
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def list_templates(user_id: str) -> list[TemplateOut]:
    if not ObjectId.is_valid(user_id):
        return []
    cursor = (
        get_db()
        .activity_templates.find({"created_by": ObjectId(user_id)})
        .sort("updated_at", -1)
    )
    return [_doc_to_template(doc) for doc in cursor]


def get_template(template_id: str, user_id: str) -> TemplateOut | None:
    if not ObjectId.is_valid(template_id) or not ObjectId.is_valid(user_id):
        return None
    doc = get_db().activity_templates.find_one(
        {"_id": ObjectId(template_id), "created_by": ObjectId(user_id)}
    )
    return _doc_to_template(doc) if doc else None


def get_template_form_data(template_id: str, user_id: str) -> TemplateFormData | None:
    template = get_template(template_id, user_id)
    if not template:
        return None
    return TemplateFormData(
        title=template.title,
        description=template.description,
        image_url=template.image_url,
        positions=template.positions,
    )


def save_template_from_activity(activity_id: str, user_id: str, template_name: str) -> TemplateOut | None:
    if not ObjectId.is_valid(activity_id) or not ObjectId.is_valid(user_id):
        return None
    name = template_name.strip()
    if not name:
        return None

    db = get_db()
    activity = db.activities.find_one(
        {"_id": ObjectId(activity_id), "created_by": ObjectId(user_id)}
    )
    if not activity:
        return None

    now = _now()
    positions = [
        {
            "name": p["name"],
            "description": p.get("description", ""),
            "capacity": p["capacity"],
        }
        for p in activity.get("positions", [])
    ]
    doc = {
        "name": name,
        "title": activity["title"],
        "description": activity.get("description", ""),
        "image_url": activity.get("image_url"),
        "positions": positions,
        "created_by": ObjectId(user_id),
        "created_at": now,
        "updated_at": now,
    }
    result = db.activity_templates.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_template(doc)


def delete_template(template_id: str, user_id: str) -> bool:
    if not ObjectId.is_valid(template_id) or not ObjectId.is_valid(user_id):
        return False
    result = get_db().activity_templates.delete_one(
        {"_id": ObjectId(template_id), "created_by": ObjectId(user_id)}
    )
    return result.deleted_count > 0


def template_positions_to_activity(positions: list[dict]) -> list[dict]:
    return [
        {
            "id": str(uuid4()),
            "name": p["name"].strip(),
            "description": p.get("description", "").strip(),
            "capacity": int(p["capacity"]),
            "participants": [],
        }
        for p in positions
        if p.get("name", "").strip()
    ]
