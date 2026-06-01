from typing import Callable

from fastapi import Depends, HTTPException, Request, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import SECRET_KEY, SESSION_COOKIE_NAME, SESSION_MAX_AGE
from app.schemas.user import UserOut
from app.services.auth_service import get_user_by_id

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="session")


def create_session_token(user_id: str) -> str:
    return _serializer.dumps({"user_id": user_id})


def read_session_token(token: str) -> str | None:
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data.get("user_id")
    except (BadSignature, SignatureExpired):
        return None


async def get_optional_user(request: Request) -> UserOut | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    user_id = read_session_token(token)
    if not user_id:
        return None
    return get_user_by_id(user_id)


async def get_current_user(user: UserOut | None = Depends(get_optional_user)) -> UserOut:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_303_SEE_OTHER,
            headers={"Location": "/login"},
        )
    return user


def require_role(*roles: str) -> Callable:
    async def dependency(user: UserOut = Depends(get_current_user)) -> UserOut:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="權限不足")
        return user

    return dependency
