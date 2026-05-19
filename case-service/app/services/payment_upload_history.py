"""ประวัติการอัปโหลด PDF 037/038 ต่อ applicant.

- มี upload_batch_id → จัดกลุ่มตาม batch (modal เดียว)
- ไม่มี batch → แยก/รวมรอบด้วย heuristic เดิม (60 วินาที)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.applicant import Applicant
from ..models.lookup import AttachmentType
from ..models.payment import FilePayment, WelfarePayment
from ..schemas.payment import (
    PaymentUploadFileItem,
    PaymentUploadHistoryRead,
    PaymentUploadHistoryRound,
)

ATTACHMENT_PDF_037_ID = 9
ATTACHMENT_PDF_038_ID = 10

FILE_LABEL_BY_ATTACHMENT_ID: dict[int, str] = {
    ATTACHMENT_PDF_037_ID: "cft037",
    ATTACHMENT_PDF_038_ID: "cft038",
}

SAME_UPLOAD_SESSION_MAX_SECONDS = 60

HistoryPaymentGroup = WelfarePayment | tuple[WelfarePayment, ...]


def _view_path(applicant_id: int, file_payment_id: int) -> str:
    return f"/v1/case_for_staff/applicant/{applicant_id}/file-payment/{file_payment_id}/file"


def _normalize_payment_number(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _history_payment_rows(all_payments: list[WelfarePayment]) -> list[WelfarePayment]:
    return [
        row
        for row in all_payments
        if row.is_037_or_038 is True or row.is_037_or_038 is False
    ]


def _rows_in_group(group: HistoryPaymentGroup) -> list[WelfarePayment]:
    if isinstance(group, tuple):
        return list(group)
    return [group]


def _group_sort_key(group: HistoryPaymentGroup) -> int:
    return min(row.id for row in _rows_in_group(group))


def _batch_id_for_group(group: HistoryPaymentGroup) -> UUID | None:
    for row in _rows_in_group(group):
        if row.upload_batch_id is not None:
            return row.upload_batch_id
    return None


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


def _group_payment_rows_legacy(payment_rows: list[WelfarePayment]) -> list[HistoryPaymentGroup]:
    groups: list[HistoryPaymentGroup] = []
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
) -> list[HistoryPaymentGroup]:
    by_batch: dict[UUID, list[WelfarePayment]] = defaultdict(list)
    for row in payment_rows:
        if row.upload_batch_id is not None:
            by_batch[row.upload_batch_id].append(row)

    groups: list[HistoryPaymentGroup] = []
    for batch_id in sorted(by_batch.keys(), key=lambda bid: min(r.id for r in by_batch[bid])):
        rows = sorted(by_batch[batch_id], key=lambda row: row.id)
        if len(rows) == 1:
            groups.append(rows[0])
        else:
            groups.append(tuple(rows))
    return groups


def _build_display_groups(payment_rows: list[WelfarePayment]) -> list[HistoryPaymentGroup]:
    with_batch = [row for row in payment_rows if row.upload_batch_id is not None]
    without_batch = [row for row in payment_rows if row.upload_batch_id is None]

    batch_groups = _group_payment_rows_by_batch(with_batch)
    legacy_groups = _group_payment_rows_legacy(without_batch)

    merged = batch_groups + legacy_groups
    merged.sort(key=_group_sort_key)
    return merged


def _payment_ids_for_group(group: HistoryPaymentGroup) -> list[int]:
    return [row.id for row in _rows_in_group(group)]


def _assign_orphan_files_to_payment_rows(
    orphan_files: list[FilePayment],
    payment_rows: list[WelfarePayment],
) -> dict[int, list[FilePayment]]:
    by_payment: dict[int, list[FilePayment]] = defaultdict(list)
    rows_by_dda: dict[int, list[WelfarePayment]] = defaultdict(list)
    for payment in payment_rows:
        rows_by_dda[payment.dda_ref_id].append(payment)

    for file_row in orphan_files:
        rows_on_dda = rows_by_dda.get(file_row.welfare_dda_ref_id, [])
        if not rows_on_dda:
            if payment_rows:
                by_payment[payment_rows[-1].id].append(file_row)
            continue
        target = rows_on_dda[0]
        for payment in rows_on_dda:
            if payment.id <= file_row.id:
                target = payment
        by_payment[target.id].append(file_row)

    return by_payment


def _collect_files_for_group(
    group: HistoryPaymentGroup,
    all_files: list[FilePayment],
    orphan_for_payments: list[FilePayment],
) -> list[FilePayment]:
    payment_id_set = set(_payment_ids_for_group(group))
    batch_id = _batch_id_for_group(group)
    seen: set[int] = set()
    collected: list[FilePayment] = []

    for file_row in all_files:
        if file_row.id in seen:
            continue
        if file_row.welfare_payment_id in payment_id_set:
            collected.append(file_row)
            seen.add(file_row.id)
            continue
        if batch_id is not None and file_row.upload_batch_id == batch_id:
            collected.append(file_row)
            seen.add(file_row.id)

    for file_row in orphan_for_payments:
        if file_row.id not in seen:
            collected.append(file_row)
            seen.add(file_row.id)

    return sorted(collected, key=lambda row: row.id)


def _resolve_file_label(
    file_row: FilePayment,
    payments_by_id: dict[int, WelfarePayment],
    attachment_names: dict[int, str],
) -> str | None:
    mapped = FILE_LABEL_BY_ATTACHMENT_ID.get(file_row.attachment_type_id)
    if mapped is not None:
        return mapped

    type_name = attachment_names.get(file_row.attachment_type_id, "").lower()
    if "037" in type_name:
        return "cft037"
    if "038" in type_name:
        return "cft038"

    linked = payments_by_id.get(file_row.welfare_payment_id or -1)
    if linked is not None:
        if linked.is_037_or_038 is False:
            return "cft037"
        if linked.is_037_or_038 is True:
            return "cft038"
    return None


def _build_round_file_items(
    applicant_id: int,
    round_files: list[FilePayment],
    payments_by_id: dict[int, WelfarePayment],
    attachment_names: dict[int, str],
) -> tuple[list[str], list[PaymentUploadFileItem]]:
    labels: list[str] = []
    file_items: list[PaymentUploadFileItem] = []
    labels_present: set[str] = set()

    for file_row in round_files:
        label = _resolve_file_label(file_row, payments_by_id, attachment_names)
        if label is None:
            continue
        if label not in labels_present:
            labels.append(label)
            labels_present.add(label)
        file_items.append(
            PaymentUploadFileItem(
                label=label,
                file_payment_id=file_row.id,
                file_original_name=file_row.file_original_name,
                view_path=_view_path(applicant_id, file_row.id),
            ),
        )

    labels = sorted(labels, key=lambda label: (label != "cft037", label))
    return labels, file_items


def _latest_uploaded_at(*rows: WelfarePayment) -> datetime | None:
    uploaded_at: datetime | None = None
    for row in rows:
        if row.created_at is None:
            continue
        if uploaded_at is None or row.created_at > uploaded_at:
            uploaded_at = row.created_at
    return uploaded_at


def _dates_for_group(rows: list[WelfarePayment]) -> tuple[date | None, date | None]:
    """วันที่ทำรายการ / วันที่มีผล — ใช้ค่าจากแถวในรอบ (มักเหมือนกันเมื่อบันทึก modal เดียว)."""
    ordered = sorted(
        rows,
        key=lambda row: (
            0 if row.is_037_or_038 is True else 1,
            row.id,
        ),
    )
    transaction_date: date | None = None
    effective_date: date | None = None
    for row in ordered:
        if transaction_date is None and row.transaction_date is not None:
            transaction_date = row.transaction_date
        if effective_date is None and row.effective_date is not None:
            effective_date = row.effective_date
    return transaction_date, effective_date


def _round_from_group(
    *,
    round_no: int,
    group: HistoryPaymentGroup,
    applicant_id: int,
    round_files: list[FilePayment],
    payments_by_id: dict[int, WelfarePayment],
    attachment_names: dict[int, str],
) -> PaymentUploadHistoryRound:
    labels, file_items = _build_round_file_items(
        applicant_id,
        round_files,
        payments_by_id,
        attachment_names,
    )
    rows = _rows_in_group(group)
    row_038 = next((row for row in rows if row.is_037_or_038 is True), None)
    row_037 = next((row for row in rows if row.is_037_or_038 is False), None)
    batch_id = _batch_id_for_group(group)
    anchor = row_038 or rows[0]

    payment_id_cft037 = (
        _normalize_payment_number(row_037.payment_number) if row_037 is not None else None
    )
    payment_id_cft038 = (
        _normalize_payment_number(row_038.payment_number) if row_038 is not None else None
    )
    if payment_id_cft038 is None and len(rows) == 1 and anchor.is_037_or_038 is True:
        payment_id_cft038 = _normalize_payment_number(anchor.payment_number)

    reason = row_038.payment_038_reason if row_038 is not None else None
    if reason is None and anchor.is_037_or_038 is True:
        reason = anchor.payment_038_reason

    transaction_date, effective_date = _dates_for_group(rows)

    return PaymentUploadHistoryRound(
        round_no=round_no,
        welfare_payment_id=anchor.id,
        payment_id_cft037=payment_id_cft037,
        payment_id_cft038=payment_id_cft038,
        files=labels,
        file_items=file_items,
        reason=reason,
        uploaded_at=_latest_uploaded_at(*rows),
        transaction_date=transaction_date,
        effective_date=effective_date,
        upload_batch_id=batch_id,
    )


async def build_payment_upload_history(
    session: AsyncSession,
    applicant_id: int,
) -> PaymentUploadHistoryRead:
    applicant = await session.get(Applicant, applicant_id)
    if applicant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="applicant_not_found")

    payments_result = await session.execute(
        select(WelfarePayment)
        .where(WelfarePayment.applicant_id == applicant_id)
        .order_by(WelfarePayment.id.asc()),
    )
    all_payments = list(payments_result.scalars().all())
    payments_by_id = {row.id: row for row in all_payments}
    payment_rows = _history_payment_rows(all_payments)

    attachment_names = {
        row.id: row.name
        for row in (
            await session.execute(select(AttachmentType))
        ).scalars().all()
    }

    linked_payment_ids = select(WelfarePayment.id).where(
        WelfarePayment.applicant_id == applicant_id,
    )
    applicant_dda_ids = select(WelfarePayment.dda_ref_id).where(
        WelfarePayment.applicant_id == applicant_id,
    )
    files_result = await session.execute(
        select(FilePayment)
        .where(
            or_(
                FilePayment.welfare_payment_id.in_(linked_payment_ids),
                and_(
                    FilePayment.welfare_payment_id.is_(None),
                    FilePayment.welfare_dda_ref_id.in_(applicant_dda_ids),
                ),
            ),
        )
        .order_by(FilePayment.id.asc()),
    )
    all_files = list(files_result.scalars().all())
    orphan_files = [row for row in all_files if row.welfare_payment_id is None]
    orphans_by_payment = _assign_orphan_files_to_payment_rows(orphan_files, payment_rows)
    display_groups = _build_display_groups(payment_rows)

    history_rounds: list[PaymentUploadHistoryRound] = []
    for round_no, group in enumerate(display_groups, start=1):
        payment_ids = _payment_ids_for_group(group)
        orphan_for_group: list[FilePayment] = []
        for payment_id in payment_ids:
            orphan_for_group.extend(orphans_by_payment.get(payment_id, []))

        round_files = _collect_files_for_group(group, all_files, orphan_for_group)
        history_rounds.append(
            _round_from_group(
                round_no=round_no,
                group=group,
                applicant_id=applicant_id,
                round_files=round_files,
                payments_by_id=payments_by_id,
                attachment_names=attachment_names,
            ),
        )

    return PaymentUploadHistoryRead(
        applicant_id=applicant_id,
        case_number=applicant.case_number,
        rounds=history_rounds,
    )
