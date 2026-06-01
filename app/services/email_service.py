import logging
import smtplib
from email.message import EmailMessage

from app.config import (
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_TLS,
    SMTP_USER,
    VERIFICATION_CODE_EXPIRE_MINUTES,
)

logger = logging.getLogger(__name__)


def send_verification_email(to_email: str, code: str) -> None:
    subject = "活動管理系統 - 電子郵件驗證碼"
    body = f"""您好，

您的驗證碼為：{code}

此驗證碼 {VERIFICATION_CODE_EXPIRE_MINUTES} 分鐘內有效。若非您本人操作，請忽略此信。

活動管理系統
"""
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP 未設定，驗證碼（僅開發用）: %s → %s", to_email, code)
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        if SMTP_USE_TLS:
            server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
