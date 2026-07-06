"""จัดกลุ่มรอบ 037/038 และคำนวณ count / display flag / cycle lock."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.payment import WelfarePayment

if TYPE_CHECKING:
    from collections.abc import Iterable

PaymentRound = WelfarePayment | tuple[WelfarePayment, ...]

SAME_UPLOAD_SESSION_MAX_SECONDS = 60


def payment_rows_for_rounds(rows: Iterable[WelfarePayment]) -> list[WelfarePayment]:
    """แถวที่ระบุประเภท 037/038 แล้ว (is_037_or_038 ไม่เป็น null)."""
    return [
        row
        for row in rows
        if row.is_037_or_038 is True or row.is_037_or_038 is False
    ]


def rows_in_round(round_group: PaymentRound) -> list[WelfarePayment]:
    if isinstance(round_group, tuple):
        return list(round_group)
    return [round_group]


def _group_sort_key(round_group: PaymentRound) -> int:
    return min(row.id for row in rows_in_round(round_group))


def batch_id_for_round(round_group: PaymentRound) -> UUID | None:
    for row in rows_in_round(round_group):
        if row.upload_batch_id is not None:
            return row.upload_batch_id
    return None


def payment_ids_for_round(round_group: PaymentRound) -> list[int]:
    return [row.id for row in rows_in_round(round_group)]


def _uploaded_in_same_session(row_038: WelfarePayment, row_037: WelfarePayment) -> bool:
    if row_037.is_037_or_038 is not False or row_038.is_037_or_038 is not True:
        return False
    if row_037.dda_ref_id != row_038.dda_ref_id:
        return False
    if row_037.id <= row_038.id:
        return False
    if row_038.created_at is None or row_037.created_at is None:
        return row_037.id == row_038.id + 1
    gap = (row_037.created_at - row_038.created_at).total_seconds()
    return 0 <= gap <= SAME_UPLOAD_SESSION_MAX_SECONDS


def _group_payment_rows_legacy(payment_rows: list[WelfarePayment]) -> list[PaymentRound]:
    groups: list[PaymentRound] = []
    index = 0
    while index < len(payment_rows):
        current = payment_rows[index]
        if (
            current.is_037_or_038 is True
            and index + 1 < len(payment_rows)
            and _uploaded_in_same_session(current, payment_rows[index + 1])
        ):
            groups.append((current, payment_rows[index + 1]))
            index += 2
            continue
        groups.append(current)
        index += 1
    return groups


def _group_payment_rows_by_batch(
    payment_rows: list[WelfarePayment],
) -> list[PaymentRound]:
    by_batch: dict[UUID, list[WelfarePayment]] = defaultdict(list)
    for row in payment_rows:
        if row.upload_batch_id is not None:
            by_batch[row.upload_batch_id].append(row)

    groups: list[PaymentRound] = []
    for batch_id in sorted(by_batch.keys(), key=lambda bid: min(r.id for r in by_batch[bid])):
        rows = sorted(by_batch[batch_id], key=lambda row: row.id)
        if len(rows) == 1:
            groups.append(rows[0])
        else:
            groups.append(tuple(rows))
    return groups


def group_payment_rounds(payment_rows: list[WelfarePayment]) -> list[PaymentRound]:
    """จัดกลุ่มรอบ — batch ก่อน แล้ว heuristic 60 วินาทีสำหรับแถวที่ไม่มี batch."""
    with_batch = [row for row in payment_rows if row.upload_batch_id is not None]
    without_batch = [row for row in payment_rows if row.upload_batch_id is None]

    batch_groups = _group_payment_rows_by_batch(with_batch)
    legacy_groups = _group_payment_rows_legacy(without_batch)

    merged = batch_groups + legacy_groups
    merged.sort(key=_group_sort_key)
    return merged


def round_has_037(round_group: PaymentRound) -> bool:
    return any(row.is_037_or_038 is False for row in rows_in_round(round_group))


def round_has_038(round_group: PaymentRound) -> bool:
    return any(row.is_037_or_038 is True for row in rows_in_round(round_group))


def round_is_037_only(round_group: PaymentRound) -> bool:
    return round_has_037(round_group) and not round_has_038(round_group)


def compute_round_counts(rounds: list[PaymentRound]) -> tuple[int, int]:
    count_037 = sum(1 for round_group in rounds if round_is_037_only(round_group))
    count_038 = sum(1 for round_group in rounds if round_has_038(round_group))
    return count_037, count_038


def latest_round_display_flag(rounds: list[PaymentRound]) -> bool | None:
    """จากรอบล่าสุด — false=037-only, true=มี 038, null=ยังไม่มีรอบที่ระบุประเภท."""
    if not rounds:
        return None
    latest = max(rounds, key=_group_sort_key)
    if round_is_037_only(latest):
        return False
    if round_has_038(latest):
        return True
    return None


def applicant_payment_metrics(payments: list[WelfarePayment]) -> dict[str, int | bool | None]:
    typed = payment_rows_for_rounds(payments)
    rounds = group_payment_rounds(typed)
    count_037, count_038 = compute_round_counts(rounds)
    return {
        "count_037": count_037,
        "count_038": count_038,
        "is_037_or_038": latest_round_display_flag(rounds),
    }


async def load_payments_for_dda(
    session: AsyncSession,
    applicant_id: int,
    dda_ref_id: int,
) -> list[WelfarePayment]:
    result = await session.execute(
        select(WelfarePayment)
        .where(
            WelfarePayment.applicant_id == applicant_id,
            WelfarePayment.dda_ref_id == dda_ref_id,
        )
        .order_by(WelfarePayment.id.asc()),
    )
    return list(result.scalars().all())


async def load_payments_by_applicant_ids(
    session: AsyncSession,
    applicant_ids: list[int],
) -> dict[int, list[WelfarePayment]]:
    if not applicant_ids:
        return {}
    result = await session.execute(
        select(WelfarePayment)
        .where(WelfarePayment.applicant_id.in_(applicant_ids))
        .order_by(WelfarePayment.applicant_id.asc(), WelfarePayment.id.asc()),
    )
    by_applicant: dict[int, list[WelfarePayment]] = defaultdict(list)
    for row in result.scalars().all():
        by_applicant[row.applicant_id].append(row)
    return dict(by_applicant)


def _find_round(
    rounds: list[PaymentRound],
    *,
    payment_id: int | None = None,
    upload_batch_id: UUID | None = None,
) -> PaymentRound | None:
    if upload_batch_id is not None:
        for round_group in rounds:
            if batch_id_for_round(round_group) == upload_batch_id:
                return round_group
    if payment_id is not None:
        for round_group in rounds:
            if payment_id in payment_ids_for_round(round_group):
                return round_group
    return None


async def round_has_038_in_dda(
    session: AsyncSession,
    applicant_id: int,
    dda_ref_id: int,
    *,
    payment_id: int | None = None,
    upload_batch_id: UUID | None = None,
) -> bool:
    """มี 038 ในรอบเดียวกับแถว 037 ที่กำลังบันทึกหรือไม่."""
    rows = await load_payments_for_dda(session, applicant_id, dda_ref_id)
    rounds = group_payment_rounds(payment_rows_for_rounds(rows))
    matched = _find_round(
        rounds,
        payment_id=payment_id,
        upload_batch_id=upload_batch_id,
    )
    if matched is None:
        return False
    return round_has_038(matched)


async def round_has_037_in_dda(
    session: AsyncSession,
    applicant_id: int,
    dda_ref_id: int,
    *,
    payment_id: int | None = None,
    upload_batch_id: UUID | None = None,
) -> bool:
    """มี 037 ในรอบเดียวกับแถว 038 ที่กำลังบันทึกหรือไม่."""
    rows = await load_payments_for_dda(session, applicant_id, dda_ref_id)
    rounds = group_payment_rounds(payment_rows_for_rounds(rows))
    matched = _find_round(
        rounds,
        payment_id=payment_id,
        upload_batch_id=upload_batch_id,
    )
    if matched is None:
        return False
    return round_has_037(matched)


async def is_dda_closed_for_038(
    session: AsyncSession,
    applicant_id: int,
    dda_ref_id: int,
) -> bool:
    """ปิดรอบ DDA — ห้ามบันทึก 038 ใหม่เมื่อมีรอบ 037-only แล้ว."""
    rows = await load_payments_for_dda(session, applicant_id, dda_ref_id)
    rounds = group_payment_rounds(payment_rows_for_rounds(rows))
    return any(round_is_037_only(round_group) for round_group in rounds)
