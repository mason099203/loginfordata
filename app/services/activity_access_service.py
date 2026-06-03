import re
import secrets
import string

from fastapi import Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import SECRET_KEY, SESSION_MAX_AGE

ACCESS_CODE_PATTERN = re.compile(r"^[A-Z0-9]{4,20}$")
_CODE_ALPHABET = string.ascii_uppercase + string.digits

_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="activity-access")


def normalize_access_code(code: str) -> str:
    return code.strip().upper()


def generate_access_code(length: int = 8) -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def generate_unique_access_code(length: int = 8) -> str:
    from app.database import get_db

    db = get_db()
    for _ in range(20):
        code = generate_access_code(length)
        if not db.activities.find_one({"access_code": code, "deleted_at": None}):
            return code
    raise RuntimeError("無法產生唯一活動代碼")


def is_valid_access_code_format(code: str) -> bool:
    return bool(ACCESS_CODE_PATTERN.match(normalize_access_code(code)))


def _cookie_name(activity_id: str) -> str:
    return f"act_access_{activity_id}"


def grant_activity_access(response: Response, activity_id: str) -> None:
    token = _serializer.dumps({"activity_id": activity_id})
    response.set_cookie(
        key=_cookie_name(activity_id),
        value=token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
    )


def has_activity_access_cookie(request: Request, activity_id: str) -> bool:
    token = request.cookies.get(_cookie_name(activity_id))
    if not token:
        return False
    try:
        data = _serializer.loads(token, max_age=SESSION_MAX_AGE)
        return data.get("activity_id") == activity_id
    except (BadSignature, SignatureExpired):
        return False
