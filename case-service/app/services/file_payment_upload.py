"""ตรวจสอบและจัดเก็บไฟล์ PDF สำหรับ file_payment."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.lookup import AttachmentType
from ..models.payment import FilePayment, WelfareDdaRef, WelfarePayment
from ..services.welfare_payment_flow import resolve_welfare_payment_for_upload
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


async def save_file_payment_pdf(
    session: AsyncSession,
    *,
    applicant_id: int,
    attachment_type_id: int,
    file: UploadFile,
    welfare_payment_id: int | None = None,
) -> FilePayment:
    payment = await resolve_welfare_payment_for_upload(
        session,
        applicant_id,
        welfare_payment_id,
    )
    welfare_dda_ref_id = payment.dda_ref_id
    await validate_welfare_dda_ref_exists(session, welfare_dda_ref_id)
    await validate_attachment_type_exists(session, attachment_type_id)
    if attachment_type_id not in ALLOWED_PAYMENT_ATTACHMENT_TYPE_IDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="attachment_type_must_be_pdf_037_or_038",
        )

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
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row
