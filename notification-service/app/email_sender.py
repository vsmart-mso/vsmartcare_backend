from __future__ import annotations

import json
import logging
import smtplib
from email.message import EmailMessage

from .settings import settings

logger = logging.getLogger(__name__)


def _maybe_login(smtp: smtplib.SMTP) -> None:
    if settings.smtp_user:
        smtp.login(settings.smtp_user, settings.smtp_password)


def send_email(
    to: str,
    subject: str,
    plain_text: str,
    html_body: str | None = None,
) -> None:
    """Send email via SMTP or log JSON when EMAIL_MODE=log."""
    if settings.email_mode == "log":
        logger.info(
            "email_send %s",
            json.dumps(
                {
                    "mode": "log",
                    "to": to,
                    "from": settings.smtp_from,
                    "subject": subject,
                    "plain_text": plain_text,
                    "html_body": html_body,
                },
                ensure_ascii=False,
            ),
        )
        return

    if settings.email_mode != "smtp":
        raise ValueError(f"unsupported EMAIL_MODE: {settings.email_mode!r}")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg.set_content(plain_text, charset="utf-8")
    if html_body:
        msg.add_alternative(html_body, subtype="html")

    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as smtp:
            _maybe_login(smtp)
            smtp.send_message(msg)
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        _maybe_login(smtp)
        smtp.send_message(msg)
