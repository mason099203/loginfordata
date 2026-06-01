from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import require_role
from app.schemas.user import UserOut
from app.services.blacklist_service import add_to_blacklist, list_blocked_users, remove_from_blacklist

router = APIRouter(tags=["blacklist"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/my/blacklist", response_class=HTMLResponse)
async def blacklist_page(
    request: Request,
    user: UserOut = Depends(require_role("advanced_user")),
):
    blocked = list_blocked_users(user.id)
    return templates.TemplateResponse(
        request,
        "activities/blacklist.html",
        {"user": user, "blocked_users": blocked, "flash": request.query_params.get("msg"), "error": None},
    )


@router.post("/my/blacklist/add")
async def blacklist_add(
    email: str = Form(...),
    user: UserOut = Depends(require_role("advanced_user")),
):
    ok, msg = add_to_blacklist(user.id, email)
    param = "msg" if ok else "error"
    return RedirectResponse(f"/my/blacklist?{param}={msg}", status_code=303)


@router.post("/my/blacklist/{target_user_id}/remove")
async def blacklist_remove(
    target_user_id: str,
    user: UserOut = Depends(require_role("advanced_user")),
):
    ok, msg = remove_from_blacklist(user.id, target_user_id)
    return RedirectResponse(f"/my/blacklist?msg={msg}", status_code=303)
