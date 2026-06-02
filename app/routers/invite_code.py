from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.dependencies import require_advanced_user
from app.schemas.user import UserOut
from app.services.invite_code_service import (
    bulk_verify_invitees,
    ensure_invite_code,
    list_pending_invitees,
    regenerate_invite_code,
    set_invite_code,
    verify_invitee,
)

router = APIRouter(tags=["invite_code"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/my/invite-code", response_class=HTMLResponse)
async def invite_code_page(
    request: Request,
    user: UserOut = Depends(require_advanced_user),
):
    ok, code_or_msg = ensure_invite_code(user.id)
    flash = request.query_params.get("msg")
    flash_type = request.query_params.get("type") or "success"
    error = None if ok else code_or_msg
    invite_code = code_or_msg if ok else None
    pending_users = list_pending_invitees(user.id)
    return templates.TemplateResponse(
        request,
        "activities/invite_code.html",
        {
            "user": user,
            "invite_code": invite_code,
            "pending_users": pending_users,
            "flash": flash,
            "flash_type": flash_type,
            "error": error,
        },
    )


@router.post("/my/invite-code/set")
async def invite_code_set(
    code: str = Form(...),
    user: UserOut = Depends(require_advanced_user),
):
    ok, msg = set_invite_code(user.id, code)
    flash_type = "success" if ok else "danger"
    return RedirectResponse(
        f"/my/invite-code?msg={quote(msg)}&type={flash_type}",
        status_code=303,
    )


@router.post("/my/invite-code/regenerate")
async def invite_code_regenerate(
    user: UserOut = Depends(require_advanced_user),
):
    ok, msg = regenerate_invite_code(user.id)
    if ok:
        msg = f"邀請碼已重設為 {msg}"
    return RedirectResponse(
        f"/my/invite-code?msg={quote(msg)}&type={'success' if ok else 'danger'}",
        status_code=303,
    )


@router.post("/my/invite-code/verify/{target_user_id}")
async def invite_code_verify_user(
    target_user_id: str,
    user: UserOut = Depends(require_advanced_user),
):
    ok, msg = verify_invitee(user.id, target_user_id)
    return RedirectResponse(
        f"/my/invite-code?msg={quote(msg)}&type={'success' if ok else 'danger'}",
        status_code=303,
    )


@router.post("/my/invite-code/bulk-verify")
async def invite_code_bulk_verify(
    user_ids: list[str] = Form(default=[]),
    user: UserOut = Depends(require_advanced_user),
):
    count, msg = bulk_verify_invitees(user.id, user_ids)
    return RedirectResponse(
        f"/my/invite-code?msg={quote(msg)}&type={'success' if count > 0 else 'danger'}",
        status_code=303,
    )
