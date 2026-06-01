from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import require_role
from app.schemas.user import UserOut
from app.services.admin_service import list_activities_filtered, list_users, update_user_role

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    user: UserOut = Depends(require_role("admin")),
):
    users = list_users()
    return templates.TemplateResponse(
        request,
        "admin/users.html",
        {"user": user, "users": users, "flash": request.query_params.get("msg")},
    )


@router.post("/users/{target_user_id}/role")
async def admin_update_role(
    target_user_id: str,
    role: str = Form(...),
    user: UserOut = Depends(require_role("admin")),
):
    ok, msg = update_user_role(target_user_id, role, user.id)
    return RedirectResponse(f"/admin/users?msg={msg}", status_code=303)


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
