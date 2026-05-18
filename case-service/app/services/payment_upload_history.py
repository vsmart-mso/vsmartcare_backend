"""ประวัติการอัปโหลด PDF 037/038 ต่อ applicant — จัดกลุ่มตามรอบ 038."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime

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


def _view_path(applicant_id: int, file_payment_id: int) -> str:
    return f"/v1/case_for_staff/applicant/{applicant_id}/file-payment/{file_payment_id}/file"


def _normalize_payment_number(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _payment_window_ids(
    anchor_038: WelfarePayment,
    all_payments: list[WelfarePayment],
    rounds_038: list[WelfarePayment],
) -> set[int]:
    """payment ids ในรอบเดียวกันบน DDA — รวมแถว 037 ที่บันทึกในรอบนั้น."""
    try:
        idx = rounds_038.index(anchor_038)
    except ValueError:
        return {anchor_038.id}

    prev_038_id = rounds_038[idx - 1].id if idx > 0 else 0
    next_038_id = rounds_038[idx + 1].id if idx + 1 < len(rounds_038) else None

    window: set[int] = set()
    for payment in all_payments:
        if payment.dda_ref_id != anchor_038.dda_ref_id:
            continue
        if payment.id <= prev_038_id:
            continue
        if next_038_id is not None and payment.id >= next_038_id:
            continue
        window.add(payment.id)
    return window


def _assign_orphan_files_to_038_rounds(
    orphan_files: list[FilePayment],
    rounds_038: list[WelfarePayment],
) -> dict[int, list[FilePayment]]:
    """ไฟล์ที่ไม่มี welfare_payment_id — ผูกรอบ 038 ตามลำดับ id บน DDA เดียวกัน."""
    by_anchor: dict[int, list[FilePayment]] = defaultdict(list)
    rounds_by_dda: dict[int, list[WelfarePayment]] = defaultdict(list)
    for payment in rounds_038:
        rounds_by_dda[payment.dda_ref_id].append(payment)

    for file_row in orphan_files:
        rounds_on_dda = rounds_by_dda.get(file_row.welfare_dda_ref_id, [])
        if not rounds_on_dda:
            continue

        target: WelfarePayment | None = None
        for idx, anchor in enumerate(rounds_on_dda):
            next_anchor_id = (
                rounds_on_dda[idx + 1].id if idx + 1 < len(rounds_on_dda) else None
            )
            prev_anchor_id = rounds_on_dda[idx - 1].id if idx > 0 else 0
            if file_row.id > prev_anchor_id and (
                next_anchor_id is None or file_row.id < next_anchor_id
            ):
                target = anchor
                break
            if file_row.id >= anchor.id and (
                next_anchor_id is None or file_row.id < next_anchor_id
            ):
                target = anchor
                break

        if target is None:
            target = rounds_on_dda[-1]
        by_anchor[target.id].append(file_row)

    return by_anchor


def _collect_round_files(
    window_ids: set[int],
    all_files: list[FilePayment],
    orphan_for_anchor: list[FilePayment],
) -> list[FilePayment]:
    seen: set[int] = set()
    collected: list[FilePayment] = []

    for file_row in all_files:
        if file_row.id in seen:
            continue
        if file_row.welfare_payment_id is not None and file_row.welfare_payment_id in window_ids:
            collected.append(file_row)
            seen.add(file_row.id)

    for file_row in orphan_for_anchor:
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


def _infer_label_for_untyped_file(
    labels_present: set[str],
    *,
    has_037_payment: bool,
) -> str:
    if "cft037" not in labels_present and has_037_payment:
        return "cft037"
    if "cft038" not in labels_present:
        return "cft038"
    if "cft037" not in labels_present:
        return "cft037"
    return "cft038"


def _build_round_file_items(
    applicant_id: int,
    round_files: list[FilePayment],
    payments_by_id: dict[int, WelfarePayment],
    attachment_names: dict[int, str],
    window_ids: set[int],
) -> tuple[list[str], list[PaymentUploadFileItem]]:
    labels: list[str] = []
    file_items: list[PaymentUploadFileItem] = []
    labels_present: set[str] = set()
    pending: list[FilePayment] = []

    has_037_payment = any(
        payments_by_id.get(pid) is not None and payments_by_id[pid].is_037_or_038 is False
        for pid in window_ids
    )

    for file_row in round_files:
        label = _resolve_file_label(file_row, payments_by_id, attachment_names)
        if label is None:
            pending.append(file_row)
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

    for file_row in pending:
        label = _infer_label_for_untyped_file(
            labels_present,
            has_037_payment=has_037_payment,
        )
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

    return labels, file_items


def _payment_number_for_037_in_round(
    window_ids: set[int],
    payments_by_id: dict[int, WelfarePayment],
) -> str | None:
    for payment_id in sorted(window_ids):
        payment = payments_by_id.get(payment_id)
        if payment is None or payment.is_037_or_038 is not False:
            continue
        number = _normalize_payment_number(payment.payment_number)
        if number is not None:
            return number
    return None


def _payment_number_for_038_in_round(
    anchor_038: WelfarePayment,
    window_ids: set[int],
    payments_by_id: dict[int, WelfarePayment],
) -> str | None:
    number = _normalize_payment_number(anchor_038.payment_number)
    if number is not None:
        return number
    for payment_id in sorted(window_ids):
        payment = payments_by_id.get(payment_id)
        if payment is None or payment.is_037_or_038 is not True:
            continue
        number = _normalize_payment_number(payment.payment_number)
        if number is not None:
            return number
    return None


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
    rounds_038 = [row for row in all_payments if row.is_037_or_038 is True]

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
    orphans_by_anchor = _assign_orphan_files_to_038_rounds(orphan_files, rounds_038)

    history_rounds: list[PaymentUploadHistoryRound] = []
    for round_no, anchor_038 in enumerate(rounds_038, start=1):
        window_ids = _payment_window_ids(anchor_038, all_payments, rounds_038)
        round_files = _collect_round_files(
            window_ids,
            all_files,
            orphans_by_anchor.get(anchor_038.id, []),
        )

        labels, file_items = _build_round_file_items(
            applicant_id,
            round_files,
            payments_by_id,
            attachment_names,
            window_ids,
        )

        uploaded_at: datetime | None = anchor_038.created_at
        for payment_id in window_ids:
            payment = payments_by_id.get(payment_id)
            if payment is not None and payment.created_at is not None:
                if uploaded_at is None or payment.created_at > uploaded_at:
                    uploaded_at = payment.created_at

        history_rounds.append(
            PaymentUploadHistoryRound(
                round_no=round_no,
                welfare_payment_id=anchor_038.id,
                payment_id_cft037=_payment_number_for_037_in_round(
                    window_ids,
                    payments_by_id,
                ),
                payment_id_cft038=_payment_number_for_038_in_round(
                    anchor_038,
                    window_ids,
                    payments_by_id,
                ),
                files=labels,
                file_items=file_items,
                reason=anchor_038.payment_038_reason,
                uploaded_at=uploaded_at,
            ),
        )

    return PaymentUploadHistoryRead(
        applicant_id=applicant_id,
        case_number=applicant.case_number,
        rounds=history_rounds,
    )
