"""ตรวจสอบและจัดเก็บไฟล์ PDF สำหรับ file_payment."""

from __future__ import annotations

import uuid
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.lookup import AttachmentType
from ..models.payment import FilePayment, WelfareDdaRef, WelfarePayment
from ..services.welfare_payment_flow import (
    file_payment_owned_by_applicant,
    resolve_welfare_payment_for_upload,
)
from ..settings import resolved_upload_root, settings

ALLOWED_PAYMENT_PDF_TYPES: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/x-pdf": ".pdf",
}

ATTACHMENT_PDF_037_ID = 9
ATTACHMENT_PDF_038_ID = 10
ALLOWED_PAYMENT_ATTACHMENT_TYPE_IDS = frozenset({ATTACHMENT_PDF_037_ID, ATTACHMENT_PDF_038_ID})


async def validate_welfare_dda_ref_exists(session: AsyncSession, welfare_dda_ref_id: int) -> WelfareDdaRef:
    row = await session.get(WelfareDdaRef, welfare_dda_ref_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="welfare_dda_ref_not_found")
    return row


async def resolve_welfare_dda_ref_id_for_applicant(session: AsyncSession, applicant_id: int) -> int:
    """หา dda_ref_id จาก welfare_payment ล่าสุดของ applicant (เรียงตาม id desc)."""
    dda_ref_id = await session.scalar(
        select(WelfarePayment.dda_ref_id)
        .where(WelfarePayment.applicant_id == applicant_id)
        .order_by(WelfarePayment.id.desc())
        .limit(1),
    )
    if dda_ref_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="welfare_payment_not_found")
    return dda_ref_id


async def validate_attachment_type_exists(session: AsyncSession, attachment_type_id: int) -> None:
    found = await session.scalar(
        select(AttachmentType.id).where(AttachmentType.id == attachment_type_id),
    )
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="attachment_type_not_found")


def file_payment_upload_root() -> Path:
    return (resolved_upload_root().parent / "file-payments").resolve()


async def _read_validated_pdf_blob(file: UploadFile) -> tuple[bytes, str]:
    raw_content_type = (file.content_type or "").split(";")[0].strip().lower()
    if raw_content_type not in ALLOWED_PAYMENT_PDF_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="unsupported_media_type_expect_pdf",
        )
    ext = ALLOWED_PAYMENT_PDF_TYPES[raw_content_type]
    blob = await file.read()
    if len(blob) > settings.max_upload_bytes:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="file_too_large")
    return blob, ext


def _delete_stored_file_if_exists(relative_path: str) -> None:
    root = file_payment_upload_root()
    path = (root / relative_path).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return
    if path.is_file():
        path.unlink(missing_ok=True)


async def _find_file_payment_for_welfare_row(
    session: AsyncSession,
    *,
    applicant_id: int,
    welfare_payment_id: int,
    attachment_type_id: int,
) -> FilePayment | None:
    row = await session.scalar(
        select(FilePayment)
        .where(
            FilePayment.welfare_payment_id == welfare_payment_id,
            FilePayment.attachment_type_id == attachment_type_id,
        )
        .order_by(FilePayment.id.desc())
        .limit(1),
    )
    if row is None:
        return None
    if not await file_payment_owned_by_applicant(session, applicant_id, row):
        return None
    return row


async def replace_file_payment_pdf(
    session: AsyncSession,
    *,
    applicant_id: int,
    file_payment_id: int,
    attachment_type_id: int,
    file: UploadFile,
    welfare_payment_id: int | None = None,
) -> FilePayment:
    """แทนที่ไฟล์ในแถว file_payment เดิม — ใช้ตอนแก้ไขประวัติ."""
    row = await session.get(FilePayment, file_payment_id)
    if row is None or not await file_payment_owned_by_applicant(session, applicant_id, row):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="file_payment_not_found")

    if row.attachment_type_id != attachment_type_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="file_payment_attachment_type_mismatch",
        )

    await validate_attachment_type_exists(session, attachment_type_id)
    if attachment_type_id not in ALLOWED_PAYMENT_ATTACHMENT_TYPE_IDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="attachment_type_must_be_pdf_037_or_038",
        )

    if welfare_payment_id is not None:
        payment = await resolve_welfare_payment_for_upload(
            session,
            applicant_id,
            welfare_payment_id,
            attachment_type_id=attachment_type_id,
        )
        row.welfare_payment_id = payment.id
        row.welfare_dda_ref_id = payment.dda_ref_id

    blob, ext = await _read_validated_pdf_blob(file)
    _delete_stored_file_if_exists(row.file_path)

    base = file_payment_upload_root()
    dest_dir = (base / str(row.welfare_dda_ref_id)).resolve()
    try:
        dest_dir.relative_to(base)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="upload_path_invalid") from e

    dest_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"
    full_path = dest_dir / stored
    full_path.write_bytes(blob)

    row.file_path = f"{row.welfare_dda_ref_id}/{stored}"
    row.file_original_name = file.filename
    row.file_stored_name = stored
    row.file_size = len(blob)
    await session.flush()
    await session.refresh(row)
    return row


async def save_file_payment_pdf(
    session: AsyncSession,
    *,
    applicant_id: int,
    attachment_type_id: int,
    file: UploadFile,
    welfare_payment_id: int | None = None,
    upload_batch_id: UUID | None = None,
    file_payment_id: int | None = None,
) -> FilePayment:
    if file_payment_id is not None:
        return await replace_file_payment_pdf(
            session,
            applicant_id=applicant_id,
            file_payment_id=file_payment_id,
            attachment_type_id=attachment_type_id,
            file=file,
            welfare_payment_id=welfare_payment_id,
        )

    if welfare_payment_id is not None and upload_batch_id is None:
        existing = await _find_file_payment_for_welfare_row(
            session,
            applicant_id=applicant_id,
            welfare_payment_id=welfare_payment_id,
            attachment_type_id=attachment_type_id,
        )
        if existing is not None:
            return await replace_file_payment_pdf(
                session,
                applicant_id=applicant_id,
                file_payment_id=existing.id,
                attachment_type_id=attachment_type_id,
                file=file,
                welfare_payment_id=welfare_payment_id,
            )
    payment = await resolve_welfare_payment_for_upload(
        session,
        applicant_id,
        welfare_payment_id,
        attachment_type_id=attachment_type_id,
    )
    welfare_dda_ref_id = payment.dda_ref_id
    await validate_welfare_dda_ref_exists(session, welfare_dda_ref_id)
    await validate_attachment_type_exists(session, attachment_type_id)
    if attachment_type_id not in ALLOWED_PAYMENT_ATTACHMENT_TYPE_IDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="attachment_type_must_be_pdf_037_or_038",
        )

    blob, ext = await _read_validated_pdf_blob(file)

    base = file_payment_upload_root()
    dest_dir = (base / str(welfare_dda_ref_id)).resolve()
    try:
        dest_dir.relative_to(base)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="upload_path_invalid") from e

    dest_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}{ext}"
    full_path = dest_dir / stored
    full_path.write_bytes(blob)

    relative_for_db = f"{welfare_dda_ref_id}/{stored}"
    row = FilePayment(
        welfare_dda_ref_id=welfare_dda_ref_id,
        welfare_payment_id=payment.id,
        attachment_type_id=attachment_type_id,
        file_path=relative_for_db,
        file_original_name=file.filename,
        file_stored_name=stored,
        file_size=len(blob),
        file_width=None,
        file_height=None,
        upload_batch_id=upload_batch_id or payment.upload_batch_id,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row
