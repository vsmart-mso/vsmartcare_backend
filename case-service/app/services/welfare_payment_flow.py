"""กฎธุรกิจ welfare_payment: ล็อก 037 ต่อ DDA, 038 หลายครั้งต่อรอบ."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.payment import FilePayment, WelfarePayment

PAYMENT_CYCLE_CLOSED = "payment_cycle_closed"


async def resolve_active_dda_ref_id(session: AsyncSession, applicant_id: int) -> int:
    """dda_ref_id จาก welfare_payment ล่าสุดของ applicant (เรียง id desc)."""
    dda_ref_id = await session.scalar(
        select(WelfarePayment.dda_ref_id)
        .where(WelfarePayment.applicant_id == applicant_id)
        .order_by(WelfarePayment.id.desc())
        .limit(1),
    )
    if dda_ref_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="welfare_payment_not_found")
    return dda_ref_id


async def has_037_for_dda(
    session: AsyncSession,
    applicant_id: int,
    dda_ref_id: int,
) -> bool:
    """มีแถว 037 (is_037_or_038 = false) ในรอบ DDA นี้หรือไม่."""
    found = await session.scalar(
        select(WelfarePayment.id)
        .where(
            WelfarePayment.applicant_id == applicant_id,
            WelfarePayment.dda_ref_id == dda_ref_id,
            WelfarePayment.is_037_or_038.is_(False),
        )
        .limit(1),
    )
    return found is not None


def _raise_cycle_closed() -> None:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=PAYMENT_CYCLE_CLOSED)


async def get_open_payment_row(
    session: AsyncSession,
    applicant_id: int,
    dda_ref_id: int,
) -> WelfarePayment | None:
    """แถว is_037_or_038 IS NULL สำหรับ PATCH 038 ครั้งแรก."""
    return await session.scalar(
        select(WelfarePayment)
        .where(
            WelfarePayment.applicant_id == applicant_id,
            WelfarePayment.dda_ref_id == dda_ref_id,
            WelfarePayment.is_037_or_038.is_(None),
        )
        .order_by(WelfarePayment.id.desc())
        .limit(1),
    )


async def _latest_payment_for_dda(
    session: AsyncSession,
    applicant_id: int,
    dda_ref_id: int,
) -> WelfarePayment | None:
    return await session.scalar(
        select(WelfarePayment)
        .where(
            WelfarePayment.applicant_id == applicant_id,
            WelfarePayment.dda_ref_id == dda_ref_id,
        )
        .order_by(WelfarePayment.id.desc())
        .limit(1),
    )


def _apply_fields(payment: WelfarePayment, updates: dict) -> None:
    for field, value in updates.items():
        setattr(payment, field, value)


async def apply_038_update(
    session: AsyncSession,
    applicant_id: int,
    updates: dict,
) -> WelfarePayment:
    """PATCH แถว null ครั้งแรก; INSERT แถวใหม่เมื่อ 038 ครั้งถัดไป."""
    dda_ref_id = await resolve_active_dda_ref_id(session, applicant_id)
    if await has_037_for_dda(session, applicant_id, dda_ref_id):
        _raise_cycle_closed()

    open_row = await get_open_payment_row(session, applicant_id, dda_ref_id)
    if open_row is not None:
        _apply_fields(open_row, updates)
        return open_row

    payment = WelfarePayment(
        applicant_id=applicant_id,
        dda_ref_id=dda_ref_id,
        is_037_or_038=updates.get("is_037_or_038", True),
        payment_number=updates.get("payment_number"),
        payment_038_reason=updates.get("payment_038_reason"),
        user_sdshv=updates.get("user_sdshv"),
        transaction_date=updates.get("transaction_date"),
        effective_date=updates.get("effective_date"),
    )
    for field, value in updates.items():
        setattr(payment, field, value)
    session.add(payment)
    await session.flush()
    return payment


async def apply_037_update(
    session: AsyncSession,
    applicant_id: int,
    updates: dict,
) -> WelfarePayment:
    """บันทึก 037 ครั้งเดียวต่อรอบ DDA — PATCH แถวเปิดหรือล่าสุด."""
    dda_ref_id = await resolve_active_dda_ref_id(session, applicant_id)
    if await has_037_for_dda(session, applicant_id, dda_ref_id):
        _raise_cycle_closed()

    target = await get_open_payment_row(session, applicant_id, dda_ref_id)
    if target is None:
        target = await _latest_payment_for_dda(session, applicant_id, dda_ref_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="welfare_payment_not_found")

    _apply_fields(target, updates)
    return target


async def apply_fields_on_active_dda(
    session: AsyncSession,
    applicant_id: int,
    updates: dict,
) -> WelfarePayment:
    """อัปเดตฟิลด์อื่นโดยไม่เปลี่ยนประเภท 037/038 — ใช้แถวล่าสุดใน DDA ปัจจุบัน."""
    dda_ref_id = await resolve_active_dda_ref_id(session, applicant_id)
    if await has_037_for_dda(session, applicant_id, dda_ref_id):
        _raise_cycle_closed()

    target = await _latest_payment_for_dda(session, applicant_id, dda_ref_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="welfare_payment_not_found")

    _apply_fields(target, updates)
    return target


async def assert_payment_cycle_open(
    session: AsyncSession,
    applicant_id: int,
) -> int:
    """คืน dda_ref_id ปัจจุบัน หรือ 403 ถ้าปิดรอบด้วย 037 แล้ว."""
    dda_ref_id = await resolve_active_dda_ref_id(session, applicant_id)
    if await has_037_for_dda(session, applicant_id, dda_ref_id):
        _raise_cycle_closed()
    return dda_ref_id


async def validate_welfare_payment_for_upload(
    session: AsyncSession,
    *,
    applicant_id: int,
    welfare_payment_id: int,
    active_dda_ref_id: int,
) -> WelfarePayment:
    payment = await session.get(WelfarePayment, welfare_payment_id)
    if payment is None or payment.applicant_id != applicant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="welfare_payment_not_found")
    if payment.dda_ref_id != active_dda_ref_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="welfare_payment_dda_mismatch",
        )
    return payment


async def resolve_welfare_payment_for_upload(
    session: AsyncSession,
    applicant_id: int,
    welfare_payment_id: int | None,
) -> WelfarePayment:
    """เลือกแถว payment สำหรับผูก file_payment."""
    active_dda_ref_id = await assert_payment_cycle_open(session, applicant_id)
    if welfare_payment_id is not None:
        return await validate_welfare_payment_for_upload(
            session,
            applicant_id=applicant_id,
            welfare_payment_id=welfare_payment_id,
            active_dda_ref_id=active_dda_ref_id,
        )

    payment = await session.scalar(
        select(WelfarePayment)
        .where(
            WelfarePayment.applicant_id == applicant_id,
            WelfarePayment.dda_ref_id == active_dda_ref_id,
        )
        .order_by(WelfarePayment.id.desc())
        .limit(1),
    )
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="welfare_payment_not_found")
    return payment


async def file_payment_owned_by_applicant(
    session: AsyncSession,
    applicant_id: int,
    file_payment: FilePayment,
) -> bool:
    row = file_payment
    if row.welfare_payment_id is not None:
        payment = await session.get(WelfarePayment, row.welfare_payment_id)
        return payment is not None and payment.applicant_id == applicant_id

    found = await session.scalar(
        select(WelfarePayment.id)
        .where(
            WelfarePayment.applicant_id == applicant_id,
            WelfarePayment.dda_ref_id == row.welfare_dda_ref_id,
        )
        .limit(1),
    )
    return found is not None
