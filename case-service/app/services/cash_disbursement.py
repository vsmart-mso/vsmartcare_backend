"""กฎเบิกจ่ายเงินสด/เช็ค — ไม่ใช้เส้น 037/038; ใช้เลขที่ขอเบิก + หลักฐาน 13/14/15."""

from __future__ import annotations

from typing import Any, Iterable

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants.attachment_types import CASH_DISBURSEMENT_PROOF_TYPE_IDS
from ..constants.current_status import CURRENT_STATUS_WITHDRAWING
from ..constants.payment_method import is_cash_or_cheque
from ..models.intake import CaseHandling, CasePayment
from ..models.payment import FilePayment, WelfarePayment


def normalize_payment_number(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def count_cash_proof_rows(file_rows: Iterable[FilePayment]) -> int:
    return sum(1 for row in file_rows if row.attachment_type_id in CASH_DISBURSEMENT_PROOF_TYPE_IDS)


def has_disbursement_proof(file_rows: Iterable[FilePayment]) -> bool:
    return count_cash_proof_rows(file_rows) > 0


def is_cash_disbursement_complete(
    *,
    payment_number: str | None,
    file_rows: Iterable[FilePayment],
) -> bool:
    return bool(normalize_payment_number(payment_number)) and has_disbursement_proof(file_rows)


async def get_case_payment_method_id(
    session: AsyncSession,
    applicant_id: int,
) -> int | None:
    return await session.scalar(
        select(CasePayment.payment_method_id)
        .join(CaseHandling, CaseHandling.id == CasePayment.case_handling_id)
        .where(CaseHandling.applicant_id == applicant_id)
        .limit(1),
    )


async def assert_transfer_payment_file_allowed(
    session: AsyncSession,
    applicant_id: int,
    attachment_type_id: int,
) -> None:
    """ห้ามอัป 037/038 บนเคสเงินสด/เช็ค (hard parity กับสมาร์ท)."""
    from ..constants.attachment_types import ATTACHMENT_TYPE_PDF_037, ATTACHMENT_TYPE_PDF_038

    if attachment_type_id not in (ATTACHMENT_TYPE_PDF_037, ATTACHMENT_TYPE_PDF_038):
        return
    method_id = await get_case_payment_method_id(session, applicant_id)
    if is_cash_or_cheque(method_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="cash_payment_does_not_use_037_038",
        )


async def assert_cash_payment_037_038_update_allowed(
    session: AsyncSession,
    applicant_id: int,
    updates: dict[str, Any],
) -> None:
    """ห้ามบันทึก is_037_or_038=true/false บนเคสเงินสด/เช็ค."""
    if updates.get("is_037_or_038") is None:
        return
    method_id = await get_case_payment_method_id(session, applicant_id)
    if is_cash_or_cheque(method_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="cash_payment_does_not_use_037_038",
        )


async def load_cash_proof_files_for_applicant(
    session: AsyncSession,
    applicant_id: int,
) -> list[FilePayment]:
    stmt = (
        select(FilePayment)
        .join(WelfarePayment, WelfarePayment.id == FilePayment.welfare_payment_id)
        .where(
            WelfarePayment.applicant_id == applicant_id,
            FilePayment.attachment_type_id.in_(tuple(CASH_DISBURSEMENT_PROOF_TYPE_IDS)),
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def load_cash_proof_files_for_dda(
    session: AsyncSession,
    applicant_id: int,
    dda_ref_id: int,
) -> list[FilePayment]:
    stmt = (
        select(FilePayment)
        .join(WelfarePayment, WelfarePayment.id == FilePayment.welfare_payment_id)
        .where(
            WelfarePayment.applicant_id == applicant_id,
            WelfarePayment.dda_ref_id == dda_ref_id,
            FilePayment.attachment_type_id.in_(tuple(CASH_DISBURSEMENT_PROOF_TYPE_IDS)),
        )
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def latest_disbursement_payment_number(
    session: AsyncSession,
    applicant_id: int,
) -> str | None:
    value = await session.scalar(
        select(WelfarePayment.payment_number)
        .where(
            WelfarePayment.applicant_id == applicant_id,
            WelfarePayment.payment_number.is_not(None),
        )
        .order_by(WelfarePayment.id.desc())
        .limit(1),
    )
    return normalize_payment_number(value)


async def cash_disbursement_metrics_for_applicant(
    session: AsyncSession,
    applicant_id: int,
    *,
    payment_method_id: int | None = None,
) -> dict[str, Any]:
    method_id = (
        payment_method_id
        if payment_method_id is not None
        else await get_case_payment_method_id(session, applicant_id)
    )
    is_cash = is_cash_or_cheque(method_id)
    proof_rows = await load_cash_proof_files_for_applicant(session, applicant_id) if is_cash else []
    payment_number = await latest_disbursement_payment_number(session, applicant_id) if is_cash else None
    count_proof = count_cash_proof_rows(proof_rows)
    return {
        "payment_method_id": method_id,
        "is_cash_payment": is_cash,
        "count_cash_proof": count_proof,
        "has_disbursement_proof": count_proof > 0,
        "disbursement_payment_number": payment_number,
        "is_cash_disbursement_complete": is_cash
        and is_cash_disbursement_complete(payment_number=payment_number, file_rows=proof_rows),
    }


def cash_disbursement_target_status(
    *,
    payment_number: str | None,
    file_rows: Iterable[FilePayment],
) -> int | None:
    if is_cash_disbursement_complete(payment_number=payment_number, file_rows=file_rows):
        return CURRENT_STATUS_WITHDRAWING
    return None
