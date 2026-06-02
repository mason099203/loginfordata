# Email 驗證碼寄信服務（目前已停用）
# 備註：Email 驗證僅能由管理員於 /admin/users 代為確認。
# 若需恢復自動寄信，請取消 app/services/auth_service.py 與 app/routers/auth.py 中的相關註解。
import json
import logging
import smtplib
import urllib.error
import urllib.request
from email.message import EmailMessage

from app.config import (
    EMAIL_FROM,
    IS_RENDER,
    RESEND_API_KEY,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_TLS,
    SMTP_USER,
    VERIFICATION_CODE_EXPIRE_MINUTES,
)

logger = logging.getLogger(__name__)


def _verification_email_content(code: str) -> tuple[str, str]:
    subject = "活動管理系統 - 電子郵件驗證碼"
    body = f"""您好，

您的驗證碼為：{code}

此驗證碼 {VERIFICATION_CODE_EXPIRE_MINUTES} 分鐘內有效。若非您本人操作，請忽略此信。

活動管理系統
"""
    return subject, body


def _send_via_resend(to_email: str, subject: str, body: str) -> None:
    payload = json.dumps(
        {
            "from": EMAIL_FROM,
            "to": [to_email],
            "subject": subject,
            "text": body,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status >= 400:
                raise RuntimeError(f"Resend API 回應 {response.status}")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Resend API 錯誤 {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Resend API 連線失敗: {exc.reason}") from exc


def _send_via_smtp(to_email: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        if SMTP_USE_TLS:
            server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)


def send_verification_email(to_email: str, code: str) -> None:
    subject, body = _verification_email_content(code)

    if RESEND_API_KEY:
        _send_via_resend(to_email, subject, body)
        logger.info("驗證信已透過 Resend 寄出: %s", to_email)
        return

    if IS_RENDER:
        raise RuntimeError(
            "Render 不支援 SMTP 寄信，請在 Environment 設定 RESEND_API_KEY 與 EMAIL_FROM"
        )

    if SMTP_USER and SMTP_PASSWORD:
        _send_via_smtp(to_email, subject, body)
        logger.info("驗證信已透過 SMTP 寄出: %s", to_email)
        return

    logger.warning("Email 未設定，驗證碼（僅開發用）: %s → %s", to_email, code)
