from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import SESSION_COOKIE_NAME, SESSION_MAX_AGE
from app.dependencies import create_session_token, get_optional_user
from app.services.auth_service import authenticate_user, create_user, get_login_verification_message

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user=Depends(get_optional_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "auth/register.html",
        {"user": None, "error": None, "invite_code": ""},
    )


@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(...),
    invite_code: str = Form(""),
):
    try:
        create_user(
            email,
            password,
            display_name,
            invite_code=invite_code.strip() or None,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"user": None, "error": str(exc), "invite_code": invite_code},
            status_code=400,
        )
    if invite_code.strip():
        return RedirectResponse("/login?registered=1&invited=1", status_code=303)
    return RedirectResponse("/login?registered=1", status_code=303)


# --- Email 驗證碼流程已停用 ---
# 備註：Email 驗證僅能由管理員於 /admin/users 頁面「代為確認 Email」。
# 若需恢復自動寄信驗證，請取消下方註解並還原 issue_verification_code 等函式。
#
# from urllib.parse import quote
# from app.services.auth_service import issue_verification_code, verify_email_code
#
# @router.get("/register/verify", response_class=HTMLResponse)
# async def verify_email_page(...):
#     ...
#
# @router.post("/register/verify")
# async def verify_email_submit(...):
#     ...
#
# @router.post("/register/resend")
# async def resend_verification(...):
#     ...


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user=Depends(get_optional_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    registered = request.query_params.get("registered")
    invited = request.query_params.get("invited")
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "user": None,
            "error": None,
            "registered": registered,
            "invited": invited,
        },
    )


@router.post("/login")
async def login_submit(
    request: Request,
    response: Response,
    email: str = Form(...),
    password: str = Form(...),
):
    user = authenticate_user(email, password)
    if not user:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "user": None,
                "error": "Email 或密碼錯誤",
                "registered": None,
                "invited": None,
            },
            status_code=400,
        )
    if not user.email_verified:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "user": None,
                "error": get_login_verification_message(email),
                "registered": None,
                "invited": None,
            },
            status_code=400,
        )
    redirect = RedirectResponse("/", status_code=303)
    redirect.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_token(user.id),
        httponly=True,
        max_age=SESSION_MAX_AGE,
        samesite="lax",
    )
    return redirect


@router.get("/logout")
async def logout():
    redirect = RedirectResponse("/login", status_code=303)
    redirect.delete_cookie(SESSION_COOKIE_NAME)
    return redirect
