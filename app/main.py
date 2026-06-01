import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pymongo.errors import PyMongoError

from app.config import UPLOAD_DIR
from app.database import ensure_indexes
from app.routers import activities, admin, auth, chat, templates as templates_router
from app.services.auth_service import bootstrap_admin

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="app/templates")


@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    try:
        ensure_indexes()
        bootstrap_admin()
    except PyMongoError as exc:
        logger.error(
            "MongoDB 連線失敗，請確認 .env 中的 MONGODB_URI 帳密與 Atlas 設定：%s",
            exc,
        )
        raise RuntimeError(
            "無法連線 MongoDB。請檢查 .env 的 MONGODB_URI（使用者名稱、密碼、IP 白名單）。"
        ) from exc
    yield


app = FastAPI(title="AVA報名表", lifespan=lifespan)


@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok"}


app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router)
app.include_router(activities.router)
app.include_router(admin.router)
app.include_router(templates_router.router)
app.include_router(chat.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if exc.status_code == 303 and exc.headers and exc.headers.get("Location"):
        return RedirectResponse(exc.headers["Location"], status_code=303)
    if exc.status_code == 403:
        return templates.TemplateResponse(
            request,
            "errors/403.html",
            {"user": None, "detail": exc.detail or "權限不足"},
            status_code=403,
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
