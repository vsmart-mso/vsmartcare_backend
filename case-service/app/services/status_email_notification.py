"""Fire-and-forget email เมื่อเจ้าหน้าที่เปลี่ยนสถานะคำร้อง (หลัง commit สำเร็จ)."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants.current_status import CURRENT_STATUS_PENDING_INTAKE
from ..models.applicant import Applicant
from ..models.lookup import CurrentStatus
from ..settings import settings

logger = logging.getLogger(__name__)


async def enqueue_status_email(
    session: AsyncSession,
    *,
    applicant_id: int,
    status_log_id: int,
    current_status_id: int,
    remarks: str | None = None,
) -> None:
    """POST ไป notification-service; ล้มเหลวแล้ว log เท่านั้น — ไม่ raise."""
    if not settings.status_email_enabled:
        return

    if current_status_id == CURRENT_STATUS_PENDING_INTAKE:
        logger.info(
            "status_email: skip applicant_id=%s status_log_id=%s "
            "(current_status_id=%s ไม่ใช่ action ของเจ้าหน้าที่)",
            applicant_id,
            status_log_id,
            current_status_id,
        )
        return

    base_url = (settings.notification_service_url or "").strip().rstrip("/")
    if not base_url:
        logger.warning("status_email: NOTIFICATION_SERVICE_URL not configured")
        return

    applicant = await session.get(Applicant, applicant_id)
    if applicant is None:
        logger.warning("status_email: applicant_id=%s not found", applicant_id)
        return

    email = (applicant.email_address or "").strip()
    if not email:
        logger.warning(
            "status_email: skipping applicant_id=%s status_log_id=%s (no email_address)",
            applicant_id,
            status_log_id,
        )
        return

    status_row = await session.get(CurrentStatus, current_status_id)
    if status_row is None:
        logger.warning(
            "status_email: current_status_id=%s not found (applicant_id=%s)",
            current_status_id,
            applicant_id,
        )
        return

    payload: dict[str, object] = {
        "status_label": status_row.description_public,
        "applicant_id": applicant_id,
        "remarks": remarks or "",
    }
    if applicant.case_number:
        payload["case_ref"] = applicant.case_number

    body = {
        "idempotency_key": f"welfare-status-{status_log_id}",
        "channel": "email",
        "to": email,
        "template_code": "WELFARE_STATUS_UPDATED",
        "payload": payload,
    }

    url = f"{base_url}/v1/notifications"
    try:
        async with httpx.AsyncClient(timeout=settings.status_email_timeout_seconds) as client:
            response = await client.post(url, json=body)
            response.raise_for_status()
    except Exception:
        logger.exception(
            "status_email: notification request failed applicant_id=%s status_log_id=%s",
            applicant_id,
            status_log_id,
        )
