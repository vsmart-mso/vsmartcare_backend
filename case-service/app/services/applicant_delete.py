"""ลบ applicant และตารางย่อย — จัดลำดับ payment/file_payment ก่อน ORM cascade."""

from __future__ import annotations

from sqlalchemy import delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.applicant import Applicant
from ..models.economic import EconomicInfo
from ..models.intake import CaseHandling
from ..models.ocr_result import OcrResult
from ..models.payment import FilePayment, WelfareDdaRef, WelfarePayment
from ..models.review import WelfareReviewComment
from ..models.status_log import WelfareRequestStatus
from ..models.welfare import WelfareHistory


def applicant_delete_load_options():  # noqa: ANN201
    """โหลดความสัมพันธ์ที่ ORM ต้องลบก่อน flush — หลีกเลี่ยง lazy load ใน async session."""
    return [
        selectinload(Applicant.addresses),
        selectinload(Applicant.economic_infos).selectinload(EconomicInfo.income_sources),
        selectinload(Applicant.dependency_loads),
        selectinload(Applicant.welfare_history).selectinload(WelfareHistory.history_details),
        selectinload(Applicant.welfare_request_types),
        selectinload(Applicant.welfare_evidences),
        selectinload(Applicant.status_logs).selectinload(WelfareRequestStatus.review_comments),
        selectinload(Applicant.approve_cases),
        selectinload(Applicant.welfare_payments),
        selectinload(Applicant.case_handling).selectinload(CaseHandling.regulation_choice),
        selectinload(Applicant.case_handling).selectinload(CaseHandling.payment),
        selectinload(Applicant.case_handling).selectinload(CaseHandling.ktb_corporate),
        selectinload(Applicant.satisfaction_surveys),
    ]


async def purge_applicant_review_comments(session: AsyncSession, applicant_id: int) -> None:
    """ลบ welfare_review_comment ก่อน status_logs — FK ไม่มี ON DELETE CASCADE ใน DB."""
    status_ids = select(WelfareRequestStatus.id).where(
        WelfareRequestStatus.applicant_id == applicant_id
    )
    await session.execute(
        delete(WelfareReviewComment).where(
            WelfareReviewComment.welfare_request_status_id.in_(status_ids)
        )
    )


async def detach_ocr_results(session: AsyncSession, applicant_id: int) -> None:
    await session.execute(
        update(OcrResult)
        .where(OcrResult.applicant_id == applicant_id)
        .values(applicant_id=None)
    )


async def purge_applicant_payment_rows(session: AsyncSession, applicant_id: int) -> None:
    """ลบ welfare_payment / file_payment / welfare_dda_ref ที่ผูก applicant (ไม่มี DB CASCADE)."""
    payment_ids = list(
        await session.scalars(
            select(WelfarePayment.id).where(WelfarePayment.applicant_id == applicant_id)
        )
    )
    dda_ref_ids = list(
        await session.scalars(
            select(WelfarePayment.dda_ref_id).where(WelfarePayment.applicant_id == applicant_id)
        )
    )
    if not payment_ids:
        return

    await session.execute(
        delete(FilePayment).where(FilePayment.welfare_payment_id.in_(payment_ids))
    )
    if dda_ref_ids:
        await session.execute(
            delete(FilePayment).where(FilePayment.welfare_dda_ref_id.in_(dda_ref_ids))
        )
    await session.execute(delete(WelfarePayment).where(WelfarePayment.applicant_id == applicant_id))
    if dda_ref_ids:
        await session.execute(
            delete(WelfareDdaRef).where(
                WelfareDdaRef.id.in_(dda_ref_ids),
                ~exists().where(WelfarePayment.dda_ref_id == WelfareDdaRef.id),
            )
        )


async def load_applicant_for_delete(session: AsyncSession, applicant_id: int) -> Applicant | None:
    stmt = (
        select(Applicant)
        .where(Applicant.id == applicant_id)
        .options(*applicant_delete_load_options())
    )
    return await session.scalar(stmt)


async def delete_applicant_cascade(session: AsyncSession, applicant_id: int) -> None:
    await purge_applicant_payment_rows(session, applicant_id)
    await purge_applicant_review_comments(session, applicant_id)
    await detach_ocr_results(session, applicant_id)
    applicant = await load_applicant_for_delete(session, applicant_id)
    if applicant is None:
        return
    await session.delete(applicant)
