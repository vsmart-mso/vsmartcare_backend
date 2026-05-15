"""ตรวจสอบข้อมูลก่อนบันทึก welfare_evidences."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants.attachment_types import ATTACHMENT_TYPE_OTHER
from ..models.lookup import AttachmentType


async def validate_welfare_evidence_upload(
    session: AsyncSession,
    attachment_type_id: int,
    file_other_type_name: str | None,
) -> str | None:
    """ตรวจ FK attachment_types และบังคับชื่อประเภทอื่นเมื่อ id = 99."""
    row = await session.execute(
        select(AttachmentType.id).where(AttachmentType.id == attachment_type_id)
    )
    if row.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="attachment_type_not_found",
        )

    if attachment_type_id == ATTACHMENT_TYPE_OTHER:
        name = (file_other_type_name or "").strip()
        if not name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="file_other_type_name_required_for_other_attachment",
            )
        return name

    if file_other_type_name and file_other_type_name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="file_other_type_name_only_for_other_attachment",
        )
    return None
