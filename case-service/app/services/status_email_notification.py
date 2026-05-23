"""Fire-and-forget email เมื่อเปลี่ยนสถานะคำร้อง (หลัง commit สำเร็จ) — ตามนโยบายฝั่งประชาชน."""

from __future__ import annotations

import logging

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants.current_status import (
    CURRENT_STATUS_AID_COMPLETED,
    PUBLIC_STATUS_PAYMENT_SUCCESS,
)
from ..models.applicant import Applicant
from ..models.lookup import PrefixType
from ..models.payment import FilePayment
from ..models.person import Person
from ..services.file_payment_upload import ATTACHMENT_PDF_037_ID
from ..models.lookup import CurrentStatus
from ..services.citizen_status_email_policy import (
    CitizenStatusEmailTrigger,
    fetch_latest_status_id,
    fetch_previous_status_id,
    resolve_public_status_label,
    should_notify_citizen_status_change,
)
from ..settings import settings

logger = logging.getLogger(__name__)

TEMPLATE_WELFARE_CASE_SUBMITTED = "WELFARE_CASE_SUBMITTED"


async def fetch_applicant_person_name(
    session: AsyncSession,
    applicant_id: int,
) -> str | None:
    """ชื่อ-สกุลพร้อมคำนำหน้า — query โดยตรง หลีกเลี่ยง lazy load บน AsyncSession."""
    row = await session.execute(
        select(PrefixType.name, Person.first_name, Person.last_name)
        .select_from(Applicant)
        .join(Person, Person.id == Applicant.persons_id)
        .join(PrefixType, PrefixType.id == Person.prefix_id)
        .where(Applicant.id == applicant_id),
    )
    data = row.one_or_none()
    if data is None:
        return None
    prefix_name, first_name, last_name = data
    prefix = (prefix_name or "").strip()
    first = (first_name or "").strip()
    last = (last_name or "").strip()
    parts = [p for p in (prefix, first, last) if p]
    return " ".join(parts) if parts else None


async def _post_notification_email(
    *,
    applicant_id: int,
    email: str,
    idempotency_key: str,
    template_code: str,
    payload: dict[str, object],
) -> None:
    base_url = (settings.notification_service_url or "").strip().rstrip("/")
    if not base_url:
        logger.warning("status_email: NOTIFICATION_SERVICE_URL not configured")
        return

    body = {
        "idempotency_key": idempotency_key,
        "channel": "email",
        "to": email,
        "template_code": template_code,
        "payload": payload,
    }

    url = f"{base_url}/v1/notifications"
    try:
        async with httpx.AsyncClient(timeout=settings.status_email_timeout_seconds) as client:
            response = await client.post(url, json=body)
            response.raise_for_status()
    except Exception:
        logger.exception(
            "status_email: notification request failed applicant_id=%s key=%s template=%s",
            applicant_id,
            idempotency_key,
            template_code,
        )


async def _post_welfare_status_email(
    *,
    applicant_id: int,
    email: str,
    idempotency_key: str,
    status_label: str,
    person_name: str | None,
    current_status_color: str | None,
    remarks: str | None,
    case_ref: str | None,
) -> None:
    payload: dict[str, object] = {
        "status_label": status_label,
        "applicant_id": applicant_id,
        "remarks": remarks or "",
    }
    if person_name:
        payload["person_name"] = person_name
        payload["citizen_name"] = person_name
    if current_status_color:
        payload["current_status_color"] = current_status_color
    if case_ref:
        payload["case_ref"] = case_ref

    await _post_notification_email(
        applicant_id=applicant_id,
        email=email,
        idempotency_key=idempotency_key,
        template_code="WELFARE_STATUS_UPDATED",
        payload=payload,
    )


async def enqueue_case_submitted_email(
    session: AsyncSession,
    *,
    applicant_id: int,
    idempotency_key: str,
    submission_kind: str,
    person_name: str | None = None,
) -> None:
    """แจ้งยืนยันการส่งคำร้อง (ครั้งแรก) หรือส่งกลับแก้ไข (correction)."""
    if not settings.status_email_enabled:
        return

    applicant = await session.get(Applicant, applicant_id)
    if applicant is None:
        logger.warning("case_submitted_email: applicant_id=%s not found", applicant_id)
        return

    email = (applicant.email_address or "").strip()
    if not email:
        logger.warning(
            "case_submitted_email: skipping applicant_id=%s (no email_address)",
            applicant_id,
        )
        return

    resolved_person_name = (person_name or "").strip() or await fetch_applicant_person_name(
        session,
        applicant_id,
    )
    payload: dict[str, object] = {
        "submission_kind": submission_kind,
        "applicant_id": applicant_id,
    }
    if resolved_person_name:
        payload["person_name"] = resolved_person_name
        payload["citizen_name"] = resolved_person_name
    if applicant.case_number:
        payload["case_ref"] = applicant.case_number

    await _post_notification_email(
        applicant_id=applicant_id,
        email=email,
        idempotency_key=idempotency_key,
        template_code=TEMPLATE_WELFARE_CASE_SUBMITTED,
        payload=payload,
    )


async def enqueue_status_email(
    session: AsyncSession,
    *,
    applicant_id: int,
    person_name: str | None = None,
    status_log_id: int,
    current_status_id: int,
    current_status_color: str | None = None,
    remarks: str | None = None,
    trigger: CitizenStatusEmailTrigger = CitizenStatusEmailTrigger.STATUS_LOG,
) -> None:
    """POST ไป notification-service; ล้มเหลวแล้ว log เท่านั้น — ไม่ raise."""
    if not settings.status_email_enabled:
        return

    previous_status_id = await fetch_previous_status_id(
        session,
        applicant_id=applicant_id,
        before_status_log_id=status_log_id,
    )
    if not should_notify_citizen_status_change(
        previous_status_id=previous_status_id,
        new_status_id=current_status_id,
        trigger=trigger,
    ):
        logger.info(
            "status_email: skipped applicant_id=%s status_log_id=%s "
            "prev=%s new=%s trigger=%s",
            applicant_id,
            status_log_id,
            previous_status_id,
            current_status_id,
            trigger.value,
        )
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

    resolved_person_name = (person_name or "").strip() or await fetch_applicant_person_name(
        session,
        applicant_id,
    )
    resolved_status_color = (current_status_color or "").strip() or (status_row.color or "").strip()
    status_label = resolve_public_status_label(
        current_status_id=current_status_id,
        description_public=status_row.description_public,
        trigger=trigger,
    )

    await _post_welfare_status_email(
        applicant_id=applicant_id,
        email=email,
        idempotency_key=f"welfare-status-{status_log_id}",
        status_label=status_label,
        person_name=resolved_person_name,
        current_status_color=resolved_status_color,
        remarks=remarks,
        case_ref=applicant.case_number,
    )


async def enqueue_payment_037_upload_email(
    session: AsyncSession,
    *,
    applicant_id: int,
    file_payment_id: int,
    person_name: str | None = None,
) -> None:
    """แจ้ง 'เบิกจ่ายสำเร็จ' เมื่ออัปโหลด PDF 037 ขณะสถานะช่วยเหลือแล้ว (id=4)."""
    if not settings.status_email_enabled:
        return

    file_row = await session.get(FilePayment, file_payment_id)
    if file_row is not None and file_row.upload_batch_id is not None:
        batch_037_count = await session.scalar(
            select(func.count(FilePayment.id)).where(
                FilePayment.upload_batch_id == file_row.upload_batch_id,
                FilePayment.attachment_type_id == ATTACHMENT_PDF_037_ID,
            ),
        )
        if (batch_037_count or 0) > 1:
            logger.info(
                "status_email: skipped 037 upload applicant_id=%s batch has %s files",
                applicant_id,
                batch_037_count,
            )
            return

    latest_status_id = await fetch_latest_status_id(session, applicant_id=applicant_id)
    if not should_notify_citizen_status_change(
        previous_status_id=latest_status_id,
        new_status_id=CURRENT_STATUS_AID_COMPLETED,
        trigger=CitizenStatusEmailTrigger.PAYMENT_037_UPLOADED,
    ):
        logger.info(
            "status_email: skipped 037 upload applicant_id=%s file_payment_id=%s latest_status=%s",
            applicant_id,
            file_payment_id,
            latest_status_id,
        )
        return

    applicant = await session.get(Applicant, applicant_id)
    if applicant is None:
        logger.warning("status_email: applicant_id=%s not found", applicant_id)
        return

    email = (applicant.email_address or "").strip()
    if not email:
        logger.warning(
            "status_email: skipping 037 upload applicant_id=%s (no email_address)",
            applicant_id,
        )
        return

    status_row = await session.get(CurrentStatus, CURRENT_STATUS_AID_COMPLETED)
    resolved_person_name = (person_name or "").strip() or await fetch_applicant_person_name(
        session,
        applicant_id,
    )
    resolved_status_color = (status_row.color if status_row else "") or "#009f75"

    await _post_welfare_status_email(
        applicant_id=applicant_id,
        email=email,
        idempotency_key=f"welfare-payment-037-{file_payment_id}",
        status_label=PUBLIC_STATUS_PAYMENT_SUCCESS,
        person_name=resolved_person_name,
        current_status_color=resolved_status_color,
        remarks="อัปโหลดเอกสารผลการจ่ายเงิน (037)",
        case_ref=applicant.case_number,
    )
