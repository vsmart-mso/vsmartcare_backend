"""บริการ article และบันทึก approve_case พร้อมเปลี่ยนสถานะ."""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.article import Article
from ..models.lookup import CurrentStatus
from ..models.payment import ApproveCase
from ..models.status_log import WelfareRequestStatus
from .esignature_storage import save_esignature_base64

_ARTICLE_CONTENT_FIELDS = (
    "service_vsmart_id",
    "phone_service",
    "at",
    "date_at",
    "title",
    "refer_vsmart_id",
    "original_story",
    "fact_story",
    "laws",
    "consider",
    "suggestion",
)


async def get_article_by_applicant_id(
    session: AsyncSession,
    applicant_id: int,
) -> Article | None:
    return await session.scalar(
        select(Article).where(Article.applicant_id == applicant_id)
    )


def _article_fields_from_payload(payload: dict) -> dict:
    return {k: payload[k] for k in _ARTICLE_CONTENT_FIELDS if k in payload}


async def upsert_article(
    session: AsyncSession,
    applicant_id: int,
    fields: dict,
) -> Article:
    """สร้างหรืออัปเดตแถว article 1:1 (ใช้ PATCH / กรณี upsert ภายใน)."""
    row = await get_article_by_applicant_id(session, applicant_id)
    content = _article_fields_from_payload(fields)
    if row is None:
        row = Article(applicant_id=applicant_id, **content)
        session.add(row)
    else:
        for key, value in content.items():
            setattr(row, key, value)
        row.updated_at = datetime.now()
    return row


async def record_approve_case_with_status(
    session: AsyncSession,
    *,
    applicant_id: int,
    approve_status: bool,
    esignature: str | None,
    user_sdshv: str | None,
    article_id: int | None = None,
) -> tuple[ApproveCase, WelfareRequestStatus, CurrentStatus]:
    """บันทึก approve_case และ welfare_request_status (caller commit แล้ว enqueue อีเมล)."""
    final_esign = save_esignature_base64(applicant_id, esignature)

    row = ApproveCase(
        applicant_id=applicant_id,
        article_id=article_id,
        approve_status=approve_status,
        esignature=final_esign,
        user_sdshv=user_sdshv,
    )
    session.add(row)

    new_status_id = 3 if approve_status else 8
    current_status = await session.scalar(
        select(CurrentStatus).where(CurrentStatus.id == new_status_id)
    )
    if current_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="current_status_not_found",
        )
    status_log = WelfareRequestStatus(
        applicant_id=applicant_id,
        current_status_id=new_status_id,
        remarks="บันทึกผลการอนุมัติเคสสำเร็จ" if approve_status else "ปฏิเสธคำร้องขอสวัสดิการ",
        update_by_sdshv=user_sdshv,
    )
    session.add(status_log)
    await session.flush()
    return row, status_log, current_status


async def resolve_article_id_for_applicant(
    session: AsyncSession,
    applicant_id: int,
) -> int | None:
    """คืน article.id ถ้ามี article ของ applicant (สำหรับ POST /approve-case เดิม)."""
    article = await get_article_by_applicant_id(session, applicant_id)
    return article.id if article is not None else None
