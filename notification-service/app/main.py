from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .settings import settings


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
    simulated: bool = True


@app.post("/v1/notifications/{message_id}/send", response_model=SendAttemptResult)
def send_notification(message_id: str, succeed: bool = True):
    """
    Starter endpoint: simulates provider send.
    In production this should be async (worker/queue) + retries.
    """
    msg = messages.get(message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="message_not_found")

    now = datetime.utcnow()
    msg.attempt_count += 1
    msg.updated_at = now
    msg.status = MessageStatus.sending

    if succeed:
        msg.status = MessageStatus.sent
        msg.last_error = None
    else:
        msg.status = MessageStatus.failed
        msg.last_error = "simulated_send_failed"

    messages[message_id] = msg
    return SendAttemptResult(message=msg, simulated=True)

