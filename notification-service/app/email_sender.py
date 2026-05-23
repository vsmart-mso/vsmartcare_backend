from __future__ import annotations

import json
import logging
import smtplib
from collections.abc import Sequence
from email.message import EmailMessage
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .email_templates.types import InlineImage
from .settings import settings

logger = logging.getLogger(__name__)


def _maybe_login(smtp: smtplib.SMTP) -> None:
    user = (settings.smtp_user or "").strip()
    password = settings.smtp_password or ""
    if not user:
        return
    if not smtp.has_extn("auth"):
        logger.warning(
            "SMTP server %s:%s does not support AUTH; skipping login (use Mailpit with empty SMTP_USER or Gmail with smtp.gmail.com)",
            settings.smtp_host,
            settings.smtp_port,
        )
        return
    smtp.login(user, password)


def _build_message(
    to: str,
    subject: str,
    plain_text: str,
    html_body: str | None,
    inline_images: Sequence[InlineImage],
) -> EmailMessage | MIMEMultipart:
    """multipart/related > alternative (plain+html) + inline images — ใช้กับ Gmail/Outlook."""
    if html_body and inline_images:
        msg: MIMEMultipart = MIMEMultipart("related")
        msg["Subject"] = subject
        msg["From"] = settings.smtp_from
        msg["To"] = to

        alternative = MIMEMultipart("alternative")
        alternative.attach(MIMEText(plain_text, "plain", "utf-8"))
        alternative.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(alternative)

        for image in inline_images:
            part = MIMEImage(image.data, _subtype=image.subtype)
            part.add_header("Content-ID", f"<{image.content_id}>")
            part.add_header("Content-Disposition", "inline", filename=image.filename)
            msg.attach(part)
        return msg

    email = EmailMessage()
    email["Subject"] = subject
    email["From"] = settings.smtp_from
    email["To"] = to
    email.set_content(plain_text, charset="utf-8")
    if html_body:
        email.add_alternative(html_body, subtype="html")
    return email


def send_email(
    to: str,
    subject: str,
    plain_text: str,
    html_body: str | None = None,
    *,
    inline_images: Sequence[InlineImage] = (),
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

    message: EmailMessage | MIMEMultipart = _build_message(
        to, subject, plain_text, html_body, inline_images
    )

    if settings.smtp_use_ssl:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as smtp:
            _maybe_login(smtp)
            smtp.send_message(message)
        return

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
            smtp.ehlo()
        _maybe_login(smtp)
        smtp.send_message(message)
