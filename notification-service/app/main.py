from __future__ import annotations

import logging
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .email_sender import send_email
from .email_sender import send_email
from .settings import settings
from .templates import render_email

logger = logging.getLogger(__name__)
from .templates import render_email

logger = logging.getLogger(__name__)


class Channel(str, Enum):
    email = "email"
    sms = "sms"
    line = "line"


class MessageStatus(str, Enum):
    queued = "queued"
    sending = "sending"
    sent = "sent"
    failed = "failed"


class NotificationRequestCreate(BaseModel):
    idempotency_key: str = Field(..., min_length=8)
    channel: Channel
    to: str = Field(..., min_length=3)
    template_code: str = Field(..., examples=["CASE_CREATED"])
    payload: Dict[str, Any] = Field(default_factory=dict)


class NotificationMessage(BaseModel):
    id: str
    request_id: str
    idempotency_key: str
    channel: Channel
    to: str
    template_code: str
    payload: Dict[str, Any]
    status: MessageStatus
    attempt_count: int
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


messages: Dict[str, NotificationMessage] = {}
idempotency_index: Dict[str, str] = {}

app = FastAPI(title=settings.service_name, version="0.1.0")


def _attempt_send_email(msg: NotificationMessage) -> NotificationMessage:
    now = datetime.utcnow()
    msg.attempt_count += 1
    msg.updated_at = now
    msg.status = MessageStatus.sending

    try:
        subject, plain_text, html_body = render_email(msg.template_code, msg.payload)
        send_email(msg.to, subject, plain_text, html_body)
        msg.status = MessageStatus.sent
        msg.last_error = None
    except Exception as exc:
        logger.exception("send_email failed message_id=%s", msg.id)
        msg.status = MessageStatus.failed
        msg.last_error = str(exc)

    msg.updated_at = datetime.utcnow()
    return msg


def _auto_send_if_enabled(msg: NotificationMessage) -> NotificationMessage:
    if not settings.email_auto_send or msg.channel != Channel.email:
        return msg
    return _attempt_send_email(msg)


@app.get("/")
def root():
    return {"service": settings.service_name, "ok": True}


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/readyz")
def readyz():
    return {"ok": True}


@app.post("/v1/notifications", response_model=NotificationMessage)
def create_notification(body: NotificationRequestCreate):
    # Idempotency: same key => return existing message
    existing_id = idempotency_index.get(body.idempotency_key)
    if existing_id:
        return messages[existing_id]

    now = datetime.utcnow()
    msg_id = str(uuid4())
    msg = NotificationMessage(
        id=msg_id,
        request_id=str(uuid4()),
        idempotency_key=body.idempotency_key,
        channel=body.channel,
        to=body.to,
        template_code=body.template_code,
        payload=body.payload,
        status=MessageStatus.queued,
        attempt_count=0,
        created_at=now,
        updated_at=now,
    )
    msg = _auto_send_if_enabled(msg)
    msg = _auto_send_if_enabled(msg)
    messages[msg_id] = msg
    idempotency_index[body.idempotency_key] = msg_id
    return msg


@app.get("/v1/notifications/{message_id}", response_model=NotificationMessage)
def get_notification(message_id: str):
    msg = messages.get(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="message_not_found")
    return msg


@app.get("/v1/notifications", response_model=List[NotificationMessage])
def list_notifications(limit: int = 50):
    return list(messages.values())[: max(1, min(limit, 200))]


class SendAttemptResult(BaseModel):
    message: NotificationMessage
    simulated: bool = False
    simulated: bool = False


@app.post("/v1/notifications/{message_id}/send", response_model=SendAttemptResult)
def send_notification(message_id: str, succeed: bool = True):
    """
    Send (or re-send) a queued message. Email channel uses EMAIL_MODE (log/smtp).
    succeed=false forces failed status (for tests).
    Send (or re-send) a queued message. Email channel uses EMAIL_MODE (log/smtp).
    succeed=false forces failed status (for tests).
    """
    msg = messages.get(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="message_not_found")

    if not succeed:
        now = datetime.utcnow()
        msg.attempt_count += 1
        msg.updated_at = now
        msg.status = MessageStatus.failed
        msg.last_error = "send_failed_by_request"
        messages[message_id] = msg
        return SendAttemptResult(message=msg, simulated=False)

    if msg.channel == Channel.email:
        msg = _attempt_send_email(msg)
        messages[message_id] = msg
        return SendAttemptResult(message=msg, simulated=settings.email_mode == "log")

    if not succeed:
        now = datetime.utcnow()
        msg.attempt_count += 1
        msg.updated_at = now
        msg.status = MessageStatus.failed
        msg.last_error = "send_failed_by_request"
        messages[message_id] = msg
        return SendAttemptResult(message=msg, simulated=False)

    if msg.channel == Channel.email:
        msg = _attempt_send_email(msg)
        messages[message_id] = msg
        return SendAttemptResult(message=msg, simulated=settings.email_mode == "log")

    now = datetime.utcnow()
    msg.attempt_count += 1
    msg.updated_at = now
    msg.status = MessageStatus.sent if succeed else MessageStatus.failed
    msg.last_error = None if succeed else "simulated_send_failed"
    msg.status = MessageStatus.sent if succeed else MessageStatus.failed
    msg.last_error = None if succeed else "simulated_send_failed"
    messages[message_id] = msg
    return SendAttemptResult(message=msg, simulated=True)
