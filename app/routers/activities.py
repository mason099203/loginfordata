from datetime import datetime
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import MAX_UPLOAD_MB, UPLOAD_DIR
from app.dependencies import get_current_user, require_role
from app.schemas.user import UserOut
from app.services.activity_service import (
    can_access_activity_chat,
    create_activity,
    get_activity,
    join_position,
    leave_position,
    list_active_activities,
    list_my_activities,
    set_activity_status,
    update_activity,
)
from app.services.template_service import get_template_form_data, list_templates

router = APIRouter(tags=["activities"])
templates = Jinja2Templates(directory="app/templates")

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _parse_positions_from_form(
    position_names: list[str],
    position_descriptions: list[str],
    position_capacities: list[str],
    position_ids: list[str] | None = None,
) -> list[dict]:
    positions = []
    for i, name in enumerate(position_names):
        if not name.strip():
            continue
        cap_str = position_capacities[i] if i < len(position_capacities) else "1"
        desc = position_descriptions[i] if i < len(position_descriptions) else ""
        pos = {
            "name": name,
            "description": desc,
            "capacity": int(cap_str),
        }
        if position_ids and i < len(position_ids) and position_ids[i]:
            pos["id"] = position_ids[i]
        positions.append(pos)
    return positions


async def _save_image(file: UploadFile | None) -> str | None:
    if not file or not file.filename:
        return None
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValueError("僅支援 JPG、PNG、GIF、WEBP 圖片")

    content = await file.read()
    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise ValueError(f"圖片大小不可超過 {MAX_UPLOAD_MB}MB")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename).suffix.lower() or ".jpg"
    filename = f"{uuid4().hex}{ext}"
    dest = UPLOAD_DIR / filename
    dest.write_bytes(content)
    return f"/static/uploads/{filename}"


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, user: UserOut = Depends(get_current_user)):
    activities = list_active_activities(user.id)
    return templates.TemplateResponse(
        request,
        "activities/list.html",
        {"user": user, "activities": activities, "flash": request.query_params.get("msg")},
    )


@router.get("/my/activities", response_class=HTMLResponse)
async def my_activities(
    request: Request,
    user: UserOut = Depends(require_role("advanced_user")),
):
    activities = list_my_activities(user.id)
    return templates.TemplateResponse(
        request,
        "activities/my_list.html",
        {"user": user, "activities": activities, "flash": request.query_params.get("msg")},
    )


@router.get("/activities/create", response_class=HTMLResponse)
async def create_activity_page(
    request: Request,
    user: UserOut = Depends(require_role("advanced_user")),
    template_id: str | None = None,
):
    template_data = None
    if template_id:
        template_data = get_template_form_data(template_id, user.id)
    return templates.TemplateResponse(
        request,
        "activities/form.html",
        {
            "user": user,
            "activity": None,
            "error": None,
            "mode": "create",
            "template_data": template_data,
            "template_id": template_id if template_data else None,
            "templates": list_templates(user.id),
        },
    )


@router.post("/activities/create")
async def create_activity_submit(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    start_time: str = Form(...),
    end_time: str = Form(...),
    position_names: list[str] = Form(default=[]),
    position_descriptions: list[str] = Form(default=[]),
    position_capacities: list[str] = Form(default=[]),
    template_image_url: str = Form(""),
    user: UserOut = Depends(require_role("advanced_user")),
):
    try:
        start = _parse_datetime(start_time)
        end = _parse_datetime(end_time)
        if end <= start:
            raise ValueError("結束時間必須晚於開始時間")
        positions = _parse_positions_from_form(
            position_names, position_descriptions, position_capacities
        )
        image_url = template_image_url.strip() or None
        activity = create_activity(
            user.id,
            title,
            description,
            start,
            end,
            image_url=image_url,
            positions=positions,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "activities/form.html",
            {
                "user": user,
                "activity": None,
                "error": str(exc),
                "mode": "create",
                "form": {"title": title, "description": description, "start_time": start_time, "end_time": end_time},
                "template_data": None,
                "template_id": None,
                "templates": list_templates(user.id),
            },
            status_code=400,
        )
    return RedirectResponse(f"/activities/{activity.id}/edit?msg=活動已建立", status_code=303)


@router.get("/activities/{activity_id}/edit", response_class=HTMLResponse)
async def edit_activity_page(
    request: Request,
    activity_id: str,
    user: UserOut = Depends(require_role("advanced_user")),
):
    activity = get_activity(activity_id, user.id)
    if not activity or activity.created_by != user.id:
        return RedirectResponse("/my/activities?msg=無權編輯此活動", status_code=303)
    return templates.TemplateResponse(
        request,
        "activities/form.html",
        {
            "user": user,
            "activity": activity,
            "error": None,
            "mode": "edit",
            "flash": request.query_params.get("msg"),
            "templates": list_templates(user.id),
        },
    )


@router.post("/activities/{activity_id}/edit")
async def edit_activity_submit(
    request: Request,
    activity_id: str,
    title: str = Form(...),
    description: str = Form(""),
    start_time: str = Form(...),
    end_time: str = Form(...),
    position_names: list[str] = Form(default=[]),
    position_descriptions: list[str] = Form(default=[]),
    position_capacities: list[str] = Form(default=[]),
    position_ids: list[str] = Form(default=[]),
    image: UploadFile | None = File(None),
    user: UserOut = Depends(require_role("advanced_user")),
):
    activity = get_activity(activity_id, user.id)
    if not activity or activity.created_by != user.id:
        return RedirectResponse("/my/activities?msg=無權編輯此活動", status_code=303)

    try:
        start = _parse_datetime(start_time)
        end = _parse_datetime(end_time)
        if end <= start:
            raise ValueError("結束時間必須晚於開始時間")

        positions = _parse_positions_from_form(
            position_names, position_descriptions, position_capacities, position_ids
        )

        new_image = await _save_image(image)
        kwargs = {
            "title": title,
            "description": description,
            "start_time": start,
            "end_time": end,
            "positions": positions,
        }
        if new_image:
            kwargs["image_url"] = new_image
        update_activity(activity_id, user.id, **kwargs)
    except (ValueError, IndexError) as exc:
        return templates.TemplateResponse(
            request,
            "activities/form.html",
            {"user": user, "activity": activity, "error": str(exc), "mode": "edit"},
            status_code=400,
        )
    return RedirectResponse(f"/activities/{activity_id}/edit?msg=已儲存", status_code=303)


@router.post("/activities/{activity_id}/status")
async def change_activity_status(
    activity_id: str,
    status_value: str = Form(..., alias="status"),
    user: UserOut = Depends(require_role("advanced_user")),
):
    result = set_activity_status(activity_id, user.id, status_value)
    if not result:
        return RedirectResponse("/my/activities?msg=無法更新狀態", status_code=303)
    labels = {"draft": "草稿", "active": "進行中", "closed": "已關閉"}
    return RedirectResponse(
        f"/activities/{activity_id}/edit?msg=狀態已更新為{labels.get(status_value, status_value)}",
        status_code=303,
    )


@router.post("/activities/{activity_id}/join/{position_id}")
async def join_activity_position(
    activity_id: str,
    position_id: str,
    user: UserOut = Depends(get_current_user),
):
    ok, msg = join_position(activity_id, position_id, user.id)
    target = f"/activities/{activity_id}?msg={msg}"
    return RedirectResponse(target, status_code=303)


@router.post("/activities/{activity_id}/leave/{position_id}")
async def leave_activity_position(
    activity_id: str,
    position_id: str,
    user: UserOut = Depends(get_current_user),
):
    ok, msg = leave_position(activity_id, position_id, user.id)
    return RedirectResponse(f"/activities/{activity_id}?msg={msg}", status_code=303)


@router.get("/activities/{activity_id}", response_class=HTMLResponse)
async def activity_detail(
    request: Request,
    activity_id: str,
    user: UserOut = Depends(get_current_user),
):
    activity = get_activity(activity_id, user.id)
    if not activity:
        return RedirectResponse("/?msg=活動不存在", status_code=303)
    can_chat = can_access_activity_chat(activity_id, user.id, user.role)
    return templates.TemplateResponse(
        request,
        "activities/detail.html",
        {"user": user, "activity": activity, "can_chat": can_chat, "flash": request.query_params.get("msg")},
    )
