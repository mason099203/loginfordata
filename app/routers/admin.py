from datetime import datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import require_role
from app.schemas.user import UserOut
from app.services.admin_service import (
    USERS_PER_PAGE,
    bulk_verify_user_emails,
    delete_user,
    list_activities_filtered,
    list_users_filtered,
    update_user_role,
    verify_user_email,
)

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


def _users_list_url(
    *,
    msg: str | None = None,
    flash_type: str | None = None,
    page: int = 1,
    keyword: str = "",
    role: str = "",
    verified: str = "",
) -> str:
    params: dict[str, str] = {}
    if msg:
        params["msg"] = msg
    if flash_type:
        params["type"] = flash_type
    if page > 1:
        params["page"] = str(page)
    if keyword.strip():
        params["keyword"] = keyword.strip()
    if role:
        params["role"] = role
    if verified:
        params["verified"] = verified
    qs = urlencode(params)
    return f"/admin/users?{qs}" if qs else "/admin/users"


def _flash_redirect(
    msg: str,
    ok: bool,
    *,
    page: int = 1,
    keyword: str = "",
    role: str = "",
    verified: str = "",
) -> RedirectResponse:
    return RedirectResponse(
        _users_list_url(
            msg=msg,
            flash_type="success" if ok else "danger",
            page=page,
            keyword=keyword,
            role=role,
            verified=verified,
        ),
        status_code=303,
    )


@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    user: UserOut = Depends(require_role("admin")),
    keyword: str | None = None,
    role: str | None = None,
    verified: str | None = None,
    page: int = 1,
):
    users, total, page, total_pages = list_users_filtered(
        keyword=keyword,
        role=role or None,
        email_verified=verified or None,
        page=page,
        per_page=USERS_PER_PAGE,
    )
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
            "filters": {
                "keyword": keyword or "",
                "role": role or "",
                "verified": verified or "",
            },
            "pagination": {
                "page": page,
                "total_pages": total_pages,
                "total": total,
                "per_page": USERS_PER_PAGE,
            },
        },
    )


@router.post("/users/{target_user_id}/role")
async def admin_update_role(
    target_user_id: str,
    role: str = Form(...),
    user: UserOut = Depends(require_role("admin")),
    return_page: int = Form(1),
    return_keyword: str = Form(""),
    return_role: str = Form(""),
    return_verified: str = Form(""),
):
    ok, msg = update_user_role(target_user_id, role, user.id)
    return _flash_redirect(
        msg, ok, page=return_page, keyword=return_keyword, role=return_role, verified=return_verified
    )


@router.post("/users/{target_user_id}/verify-email")
async def admin_verify_email(
    target_user_id: str,
    user: UserOut = Depends(require_role("admin")),
    return_page: int = Form(1),
    return_keyword: str = Form(""),
    return_role: str = Form(""),
    return_verified: str = Form(""),
):
    ok, msg = verify_user_email(target_user_id)
    return _flash_redirect(
        msg, ok, page=return_page, keyword=return_keyword, role=return_role, verified=return_verified
    )


@router.post("/users/bulk-verify-email")
async def admin_bulk_verify_email(
    user_ids: list[str] = Form(default=[]),
    user: UserOut = Depends(require_role("admin")),
    return_page: int = Form(1),
    return_keyword: str = Form(""),
    return_role: str = Form(""),
    return_verified: str = Form(""),
):
    count, msg = bulk_verify_user_emails(user_ids, user.id)
    return _flash_redirect(
        msg,
        count > 0,
        page=return_page,
        keyword=return_keyword,
        role=return_role,
        verified=return_verified,
    )


@router.post("/users/{target_user_id}/delete")
async def admin_delete_user(
    target_user_id: str,
    user: UserOut = Depends(require_role("admin")),
    return_page: int = Form(1),
    return_keyword: str = Form(""),
    return_role: str = Form(""),
    return_verified: str = Form(""),
):
    ok, msg = delete_user(target_user_id, user.id)
    return _flash_redirect(
        msg, ok, page=return_page, keyword=return_keyword, role=return_role, verified=return_verified
    )


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
