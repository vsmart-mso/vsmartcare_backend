"""Satisfaction survey API — บันทึกและดึงผลประเมินความพึงพอใจ.

Endpoints:
  POST /v1/satisfaction          — บันทึกผลประเมิน
  GET  /v1/satisfaction/{id}     — ดูผลประเมินตาม id
  GET  /v1/satisfaction          — ดูผลประเมินทั้งหมดของ applicant_id (query param)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_session
from ...models.applicant import Applicant
from ...models.satisfaction import SatisfactionSurvey
from ...schemas.satisfaction import SatisfactionSurveyCreate, SatisfactionSurveyRead

router = APIRouter(prefix="/v1/satisfaction", tags=["satisfaction"])


@router.post(
    "",
    response_model=SatisfactionSurveyRead,
    status_code=status.HTTP_201_CREATED,
    summary="บันทึกผลประเมินความพึงพอใจ",
)
async def create_satisfaction_survey(
    body: SatisfactionSurveyCreate,
    session: AsyncSession = Depends(get_session),
) -> SatisfactionSurvey:
    applicant = await session.get(Applicant, body.applicant_id)
    if not applicant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ไม่พบ applicant id={body.applicant_id}",
        )

    survey = SatisfactionSurvey(
        applicant_id=body.applicant_id,
        survey_type=body.survey_type,
        rating=body.rating,
        comment=body.comment,
    )
    session.add(survey)
    await session.commit()
    await session.refresh(survey)
    return survey


@router.get(
    "",
    response_model=list[SatisfactionSurveyRead],
    summary="ดูผลประเมินทั้งหมดของ applicant",
)
async def list_satisfaction_surveys(
    applicant_id: int = Query(..., ge=1),
    session: AsyncSession = Depends(get_session),
) -> list[SatisfactionSurvey]:
    result = await session.execute(
        select(SatisfactionSurvey)
        .where(SatisfactionSurvey.applicant_id == applicant_id)
        .order_by(SatisfactionSurvey.created_at)
    )
    return list(result.scalars().all())
