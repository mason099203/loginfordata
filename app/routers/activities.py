from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import app_now
from app.dependencies import get_current_user, require_role
from app.schemas.user import UserOut
from app.services.activity_service import (
    can_access_activity_chat,
    create_activity,
    delete_activity,
    get_activity,
    join_position,
    leave_position,
    list_active_activities,
    list_my_activities,
    set_activity_status,
    update_activity,
)
from app.schemas.activity import ACTIVATE_DURATION_OPTIONS
from app.services.blacklist_service import is_user_blocked
from app.services.registration_log_service import list_registration_logs
from app.services.chat_service import get_recent_messages
from app.services.template_service import get_template_form_data, list_templates

router = APIRouter(tags=["activities"])
templates = Jinja2Templates(directory="app/templates")


def _default_start_time_value() -> str:
    return app_now().replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M")


def _parse_start_time(value: str) -> datetime | None:
    cleaned = value.strip()
    if not cleaned:
        return None
    return datetime.fromisoformat(cleaned)


def _parse_image_url(value: str) -> str | None:
    url = value.strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        raise ValueError("圖片連結必須以 http:// 或 https:// 開頭")
    return url


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
        {
            "user": user,
            "activities": activities,
            "flash": request.query_params.get("msg"),
            "duration_options": ACTIVATE_DURATION_OPTIONS,
            "default_start_time": _default_start_time_value(),
        },
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
    position_names: list[str] = Form(default=[]),
    position_descriptions: list[str] = Form(default=[]),
    position_capacities: list[str] = Form(default=[]),
    image_url: str = Form(""),
    user: UserOut = Depends(require_role("advanced_user")),
):
    try:
        positions = _parse_positions_from_form(
            position_names, position_descriptions, position_capacities
        )
        parsed_image = _parse_image_url(image_url)
        activity = create_activity(
            user.id,
            title,
            description,
            image_url=parsed_image,
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
                "form": {"title": title, "description": description, "image_url": image_url},
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
            "can_view_logs": True,
            "registration_logs": list_registration_logs(activity_id),
            "duration_options": ACTIVATE_DURATION_OPTIONS,
            "default_start_time": _default_start_time_value(),
        },
    )


@router.post("/activities/{activity_id}/edit")
async def edit_activity_submit(
    request: Request,
    activity_id: str,
    title: str = Form(...),
    description: str = Form(""),
    position_names: list[str] = Form(default=[]),
    position_descriptions: list[str] = Form(default=[]),
    position_capacities: list[str] = Form(default=[]),
    position_ids: list[str] = Form(default=[]),
    image_url: str = Form(""),
    user: UserOut = Depends(require_role("advanced_user")),
):
    activity = get_activity(activity_id, user.id)
    if not activity or activity.created_by != user.id:
        return RedirectResponse("/my/activities?msg=無權編輯此活動", status_code=303)

    try:
        positions = _parse_positions_from_form(
            position_names, position_descriptions, position_capacities, position_ids
        )
        parsed_image = _parse_image_url(image_url)
        update_activity(
            activity_id,
            user.id,
            title=title,
            description=description,
            positions=positions,
            image_url=parsed_image,
            set_image_url=True,
        )
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
    duration_hours: int = Form(3),
    start_time: str = Form(""),
    redirect_to: str = Form(""),
    user: UserOut = Depends(require_role("advanced_user")),
):
    parsed_start = None
    if status_value == "active" and start_time.strip():
        try:
            parsed_start = _parse_start_time(start_time)
        except ValueError:
            if redirect_to:
                sep = "&" if "?" in redirect_to else "?"
                return RedirectResponse(f"{redirect_to}{sep}msg=開始時間格式不正確", status_code=303)
            return RedirectResponse(
                f"/activities/{activity_id}/edit?msg=開始時間格式不正確",
                status_code=303,
            )
    elif status_value == "active":
        parsed_start = None
    result = set_activity_status(
        activity_id,
        user.id,
        status_value,
        duration_hours,
        start_time=parsed_start,
    )
    if not result:
        if redirect_to:
            sep = "&" if "?" in redirect_to else "?"
            return RedirectResponse(f"{redirect_to}{sep}msg=無法更新狀態", status_code=303)
        return RedirectResponse("/my/activities?msg=無法更新狀態", status_code=303)
    labels = {"draft": "草稿", "active": "進行中", "closed": "已關閉"}
    msg = labels.get(status_value, status_value)
    if status_value == "active":
        start_label = result.start_time.strftime("%Y-%m-%d %H:%M")
        msg = f"進行中（{start_label} 起，{duration_hours} 小時）"
    if redirect_to:
        sep = "&" if "?" in redirect_to else "?"
        target = f"{redirect_to}{sep}msg=狀態已更新為{msg}"
    else:
        target = f"/activities/{activity_id}/edit?msg=狀態已更新為{msg}"
    return RedirectResponse(target, status_code=303)


@router.post("/activities/{activity_id}/delete")
async def delete_activity_route(
    activity_id: str,
    user: UserOut = Depends(require_role("advanced_user")),
):
    if not delete_activity(activity_id, user.id):
        return RedirectResponse("/my/activities?msg=無法刪除活動", status_code=303)
    return RedirectResponse("/my/activities?msg=活動已刪除", status_code=303)


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
    activity = get_activity(
        activity_id,
        user.id,
        include_deleted=user.role == "admin",
    )
    if not activity:
        return RedirectResponse("/?msg=活動不存在", status_code=303)
    can_chat = can_access_activity_chat(activity_id, user.id, user.role)
    chat_messages = get_recent_messages("activity", activity_id) if can_chat else []
    is_blacklisted = is_user_blocked(activity.created_by, user.id)
    can_view_logs = user.role == "admin" or activity.created_by == user.id
    registration_logs = list_registration_logs(activity_id) if can_view_logs else []
    return templates.TemplateResponse(
        request,
        "activities/detail.html",
        {
            "user": user,
            "activity": activity,
            "can_chat": can_chat,
            "chat_messages": chat_messages,
            "is_blacklisted": is_blacklisted,
            "can_view_logs": can_view_logs,
            "registration_logs": registration_logs,
            "flash": request.query_params.get("msg"),
        },
    )
