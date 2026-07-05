"""นโยบายอีเมลแจ้งสถานะฝั่งประชาชน (WELFARE_STATUS_UPDATED)."""

from __future__ import annotations

from enum import Enum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants.current_status import (
    CURRENT_STATUS_AID_COMPLETED,
    CURRENT_STATUS_EDIT_REQUESTED,
    CURRENT_STATUS_INELIGIBLE,
    CURRENT_STATUS_PENDING_INTAKE,
    CURRENT_STATUS_RECEIVED,
    CURRENT_STATUS_WITHDRAWING,
    CURRENT_STATUS_WITHDRAWING_APPROVED,
    PUBLIC_STATUS_PAYMENT_SUCCESS,
)

# แจ้งทุกครั้งที่เปลี่ยนเป็นสถานะเหล่านี้ (ยกเว้นบันทึกซ้ำสถานะเดิม)
_ALWAYS_NOTIFY_STATUS_IDS: frozenset[int] = frozenset({
    CURRENT_STATUS_EDIT_REQUESTED,
    CURRENT_STATUS_INELIGIBLE,
})
from ..models.status_log import WelfareRequestStatus

# ลำดับความคืบหน้าหลักของ workflow (ยกเว้นแก้ไขข้อมูล)
_WORKFLOW_RANK: dict[int, int] = {
    CURRENT_STATUS_PENDING_INTAKE: 10,
    CURRENT_STATUS_RECEIVED: 20,
    CURRENT_STATUS_WITHDRAWING_APPROVED: 30,
    CURRENT_STATUS_WITHDRAWING: 40,
    CURRENT_STATUS_AID_COMPLETED: 50,
}

# สถานะที่แจ้งประชาชนเมื่อเดินหน้า (ไม่นับรอรับเรื่อง / เบิกจ่ายสำเร็จ — มีเทมเพลตแยก)
_NOTIFY_FORWARD_STATUS_IDS: frozenset[int] = frozenset({
    CURRENT_STATUS_RECEIVED,
    CURRENT_STATUS_WITHDRAWING_APPROVED,
    CURRENT_STATUS_EDIT_REQUESTED,
})

# แจ้งเฉพาะเมื่อเปลี่ยนจากสถานะก่อนหน้าที่กำหนด (กันแจ้งซ้ำ / ย้อนแล้วเลือกสถานะเดิมอีกครั้ง)
_NOTIFY_ALLOWED_PREVIOUS: dict[int, frozenset[int]] = {
    # รับเรื่องแล้ว: แจ้งครั้งเดียวเมื่อมาจากรอรับเรื่องเท่านั้น
    CURRENT_STATUS_RECEIVED: frozenset({CURRENT_STATUS_PENDING_INTAKE}),
    # อยู่ระหว่างการเบิก: หลังรับเรื่องแล้ว (หรืออนุมัติเคสจากสถานะ 2)
    CURRENT_STATUS_WITHDRAWING_APPROVED: frozenset({CURRENT_STATUS_RECEIVED}),
}


class CitizenStatusEmailTrigger(str, Enum):
    """แหล่งที่มาของการพิจารณาส่งอีเมล."""

    STATUS_LOG = "status_log"
    PAYMENT_037_RECORDED = "payment_037_recorded"
    PAYMENT_037_UPLOADED = "payment_037_uploaded"


async def fetch_previous_status_id(
    session: AsyncSession,
    *,
    applicant_id: int,
    before_status_log_id: int,
) -> int | None:
    """สถานะก่อนบันทึกล่าสุด (ไม่รวมแถว before_status_log_id)."""
    return await session.scalar(
        select(WelfareRequestStatus.current_status_id)
        .where(
            WelfareRequestStatus.applicant_id == applicant_id,
            WelfareRequestStatus.id < before_status_log_id,
        )
        .order_by(WelfareRequestStatus.id.desc())
        .limit(1),
    )


async def fetch_latest_status_id(
    session: AsyncSession,
    *,
    applicant_id: int,
) -> int | None:
    """สถานะล่าสุดของคำร้อง."""
    return await session.scalar(
        select(WelfareRequestStatus.current_status_id)
        .where(WelfareRequestStatus.applicant_id == applicant_id)
        .order_by(WelfareRequestStatus.updated_at.desc(), WelfareRequestStatus.id.desc())
        .limit(1),
    )


def _is_workflow_rollback(previous_status_id: int | None, new_status_id: int) -> bool:
    if previous_status_id is None:
        return False
    if new_status_id in _ALWAYS_NOTIFY_STATUS_IDS:
        return False
    if previous_status_id == CURRENT_STATUS_EDIT_REQUESTED and new_status_id == CURRENT_STATUS_PENDING_INTAKE:
        return False
    prev_rank = _WORKFLOW_RANK.get(previous_status_id)
    new_rank = _WORKFLOW_RANK.get(new_status_id)
    if prev_rank is None or new_rank is None:
        return False
    return new_rank < prev_rank


def should_notify_citizen_status_change(
    *,
    previous_status_id: int | None,
    new_status_id: int,
    trigger: CitizenStatusEmailTrigger = CitizenStatusEmailTrigger.STATUS_LOG,
) -> bool:
    """ตัดสินว่าควรส่งอีเมลแจ้งประชาชนหรือไม่."""
    if trigger == CitizenStatusEmailTrigger.PAYMENT_037_RECORDED:
        return new_status_id == CURRENT_STATUS_WITHDRAWING

    if trigger == CitizenStatusEmailTrigger.PAYMENT_037_UPLOADED:
        return previous_status_id == CURRENT_STATUS_AID_COMPLETED

    if new_status_id in _ALWAYS_NOTIFY_STATUS_IDS:
        if previous_status_id is not None and previous_status_id == new_status_id:
            return False
        return True

    if new_status_id == CURRENT_STATUS_AID_COMPLETED:
        return False

    if new_status_id == CURRENT_STATUS_WITHDRAWING:
        return False

    if new_status_id not in _NOTIFY_FORWARD_STATUS_IDS:
        return False

    if previous_status_id is not None and previous_status_id == new_status_id:
        return False

    if _is_workflow_rollback(previous_status_id, new_status_id):
        return False

    allowed_previous = _NOTIFY_ALLOWED_PREVIOUS.get(new_status_id)
    if allowed_previous is not None:
        return previous_status_id in allowed_previous

    return True


def is_status_advancement(current_status_id: int | None, target_status_id: int) -> bool:
    """คืน True เมื่อ target_status_id เดินหน้าในลำดับ workflow (rank สูงขึ้น).

    คืน False เมื่อ target เท่าเดิมหรือถอยหลัง — ใช้ guard ก่อนบันทึก status log.
    """
    if current_status_id is None:
        return True
    current_rank = _WORKFLOW_RANK.get(current_status_id, 0)
    target_rank = _WORKFLOW_RANK.get(target_status_id, 0)
    return target_rank > current_rank


def resolve_public_status_label(
    *,
    current_status_id: int,
    description_public: str,
    trigger: CitizenStatusEmailTrigger = CitizenStatusEmailTrigger.STATUS_LOG,
) -> str:
    """ข้อความสถานะในอีเมล — บังคับ 'เบิกจ่ายสำเร็จ' ตามเงื่อนไขธุรกิจ."""
    if trigger in (
        CitizenStatusEmailTrigger.PAYMENT_037_RECORDED,
        CitizenStatusEmailTrigger.PAYMENT_037_UPLOADED,
    ):
        return PUBLIC_STATUS_PAYMENT_SUCCESS
    if current_status_id == CURRENT_STATUS_WITHDRAWING:
        return PUBLIC_STATUS_PAYMENT_SUCCESS
    return description_public
