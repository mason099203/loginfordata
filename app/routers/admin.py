from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import require_role
from app.schemas.user import UserOut
from app.services.admin_service import (
    bulk_verify_user_emails,
    delete_user,
    list_activities_filtered,
    list_users,
    update_user_role,
    verify_user_email,
)

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


def _flash_redirect(msg: str, ok: bool) -> RedirectResponse:
    flash_type = "success" if ok else "danger"
    return RedirectResponse(
        f"/admin/users?msg={quote(msg)}&type={flash_type}",
        status_code=303,
    )


@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    user: UserOut = Depends(require_role("admin")),
):
    users = list_users()
    flash_type = request.query_params.get("type") or "info"
    if flash_type not in ("success", "danger", "info", "warning"):
        flash_type = "info"
    return templates.TemplateResponse(
        request,
        "admin/users.html",
        {
            "user": user,
            "users": users,
            "flash": request.query_params.get("msg"),
            "flash_type": flash_type,
        },
    )


@router.post("/users/{target_user_id}/role")
async def admin_update_role(
    target_user_id: str,
    role: str = Form(...),
    user: UserOut = Depends(require_role("admin")),
):
    ok, msg = update_user_role(target_user_id, role, user.id)
    return _flash_redirect(msg, ok)


@router.post("/users/{target_user_id}/verify-email")
async def admin_verify_email(
    target_user_id: str,
    user: UserOut = Depends(require_role("admin")),
):
    ok, msg = verify_user_email(target_user_id)
    return _flash_redirect(msg, ok)


@router.post("/users/bulk-verify-email")
async def admin_bulk_verify_email(
    user_ids: list[str] = Form(default=[]),
    user: UserOut = Depends(require_role("admin")),
):
    count, msg = bulk_verify_user_emails(user_ids, user.id)
    return _flash_redirect(msg, count > 0)


@router.post("/users/{target_user_id}/delete")
async def admin_delete_user(
    target_user_id: str,
    user: UserOut = Depends(require_role("admin")),
):
    ok, msg = delete_user(target_user_id, user.id)
    return _flash_redirect(msg, ok)


@router.get("/activities", response_class=HTMLResponse)
async def admin_activities(
    request: Request,
    user: UserOut = Depends(require_role("admin")),
    status: str | None = None,
    keyword: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    parsed_from = datetime.fromisoformat(date_from) if date_from else None
    parsed_to = datetime.fromisoformat(date_to) if date_to else None
    activities = list_activities_filtered(
        status=status or None,
        keyword=keyword or None,
        date_from=parsed_from,
        date_to=parsed_to,
    )
    return templates.TemplateResponse(
        request,
        "admin/activities.html",
        {
            "user": user,
            "activities": activities,
            "filters": {
                "status": status or "",
                "keyword": keyword or "",
                "date_from": date_from or "",
                "date_to": date_to or "",
            },
        },
    )
