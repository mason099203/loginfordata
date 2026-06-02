import json
from collections import defaultdict

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import SESSION_COOKIE_NAME
from app.dependencies import get_current_user, read_session_token
from app.schemas.user import UserOut
from app.services.activity_service import can_access_activity_chat, get_activity
from app.services.auth_service import get_user_by_id
from app.services.chat_service import get_recent_messages, save_message

router = APIRouter(tags=["chat"])
templates = Jinja2Templates(directory="app/templates")

rooms: dict[str, set[WebSocket]] = defaultdict(set)


def _room_key(room_type: str, room_id: str | None) -> str:
    return f"{room_type}:{room_id or 'global'}"


async def _broadcast(room_key: str, payload: dict):
    dead = []
    for ws in rooms[room_key]:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        rooms[room_key].discard(ws)


@router.get("/chat/global", response_class=HTMLResponse)
async def global_chat_page(request: Request, user: UserOut = Depends(get_current_user)):
    messages = get_recent_messages("global")
    return templates.TemplateResponse(
        request,
        "chat/room.html",
        {
            "user": user,
            "room_type": "global",
            "room_id": None,
            "room_title": "聊天室",
            "messages": messages,
        },
    )


@router.get("/chat/activity/{activity_id}", response_class=HTMLResponse)
async def activity_chat_page(
    request: Request,
    activity_id: str,
    user: UserOut = Depends(get_current_user),
):
    if not can_access_activity_chat(activity_id, user.id, user.role):
        activity = get_activity(activity_id)
        title = activity.title if activity else "活動"
        return templates.TemplateResponse(
            request,
            "chat/denied.html",
            {"user": user, "activity_title": title},
            status_code=403,
        )
    activity = get_activity(activity_id)
    messages = get_recent_messages("activity", activity_id)
    return templates.TemplateResponse(
        request,
        "chat/room.html",
        {
            "user": user,
            "room_type": "activity",
            "room_id": activity_id,
            "room_title": f"{activity.title} 聊天室" if activity else "活動聊天室",
            "messages": messages,
        },
    )


@router.get("/api/chat/{room_type}/messages")
async def api_messages(
    room_type: str,
    room_id: str | None = None,
    user: UserOut = Depends(get_current_user),
):
    if room_type == "activity":
        if not room_id or not can_access_activity_chat(room_id, user.id, user.role):
            return {"messages": []}
    messages = get_recent_messages(room_type, room_id)
    return {
        "messages": [
            {
                "id": m.id,
                "sender_name": m.sender_name,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ]
    }


@router.websocket("/ws/chat/{room_type}")
@router.websocket("/ws/chat/{room_type}/{room_id}")
async def chat_websocket(websocket: WebSocket, room_type: str, room_id: str | None = None):
    token = websocket.cookies.get(SESSION_COOKIE_NAME)
    user_id = read_session_token(token) if token else None
    user = get_user_by_id(user_id) if user_id else None
    if not user:
        await websocket.close(code=4401)
        return

    if room_type not in ("global", "activity"):
        await websocket.close(code=4400)
        return

    if room_type == "activity":
        if not room_id or not can_access_activity_chat(room_id, user.id, user.role):
            await websocket.close(code=4403)
            return

    await websocket.accept()
    key = _room_key(room_type, room_id)
    rooms[key].add(websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
                content = str(data.get("content", "")).strip()
            except json.JSONDecodeError:
                content = raw.strip()
            if not content:
                continue

            msg = save_message(room_type, room_id, user.id, user.display_name, content)
            payload = {
                "id": msg.id,
                "sender_name": msg.sender_name,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            }
            await _broadcast(key, payload)
    except WebSocketDisconnect:
        rooms[key].discard(websocket)
