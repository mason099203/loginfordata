from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.config import SESSION_COOKIE_NAME, SESSION_MAX_AGE
from app.dependencies import create_session_token, get_optional_user
from app.services.auth_service import authenticate_user, create_user

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
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "auth/register.html",
            {"user": None, "error": str(exc)},
            status_code=400,
        )
    return RedirectResponse("/login?registered=1", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user=Depends(get_optional_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    registered = request.query_params.get("registered")
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {"user": None, "error": None, "registered": registered},
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
            {"user": None, "error": "Email 或密碼錯誤", "registered": None},
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
