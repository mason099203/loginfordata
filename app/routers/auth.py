from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import SESSION_COOKIE_NAME, SESSION_MAX_AGE
from app.dependencies import create_session_token, get_optional_user
from app.services.auth_service import (
    authenticate_user,
    create_user,
    issue_verification_code,
    verify_email_code,
)

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user=Depends(get_optional_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "auth/register.html",
        {"user": None, "error": None},
    )


@router.post("/register")
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(...),
):
    try:
        create_user(email, password, display_name)
        issue_verification_code(email)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"user": None, "error": str(exc)},
            status_code=400,
        )
    except Exception:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"user": None, "error": "驗證信寄送失敗，請稍後再試"},
            status_code=500,
        )
    return RedirectResponse(f"/register/verify?email={quote(email.lower().strip())}", status_code=303)


@router.get("/register/verify", response_class=HTMLResponse)
async def verify_email_page(
    request: Request,
    email: str | None = None,
    user=Depends(get_optional_user),
):
    if user:
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "auth/verify_email.html",
        {"user": None, "email": email or "", "error": None, "success": None},
    )


@router.post("/register/verify")
async def verify_email_submit(
    request: Request,
    email: str = Form(...),
    code: str = Form(...),
):
    ok, msg = verify_email_code(email, code)
    if not ok:
        return templates.TemplateResponse(
            request,
            "auth/verify_email.html",
            {"user": None, "email": email, "error": msg, "success": None},
            status_code=400,
        )
    return RedirectResponse("/login?verified=1", status_code=303)


@router.post("/register/resend")
async def resend_verification(
    request: Request,
    email: str = Form(...),
):
    try:
        issue_verification_code(email)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "auth/verify_email.html",
            {"user": None, "email": email, "error": str(exc), "success": None},
            status_code=400,
        )
    except Exception:
        return templates.TemplateResponse(
            request,
            "auth/verify_email.html",
            {"user": None, "email": email, "error": "驗證信寄送失敗，請稍後再試", "success": None},
            status_code=500,
        )
    return templates.TemplateResponse(
        request,
        "auth/verify_email.html",
        {"user": None, "email": email, "error": None, "success": "驗證碼已重新寄出，請查收 Email"},
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user=Depends(get_optional_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    registered = request.query_params.get("registered")
    verified = request.query_params.get("verified")
    pending_email = request.query_params.get("email")
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "user": None,
            "error": None,
            "registered": registered,
            "verified": verified,
            "pending_email": pending_email,
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
                "verified": None,
                "pending_email": None,
            },
            status_code=400,
        )
    if not user.email_verified:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "user": None,
                "error": "Email 尚未驗證，請先輸入驗證碼或聯絡管理員代為確認",
                "registered": None,
                "verified": None,
                "pending_email": user.email,
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
