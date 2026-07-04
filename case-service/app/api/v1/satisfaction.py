"""Satisfaction survey API — บันทึกและดึงผลประเมินความพึงพอใจ.

Endpoints:
  POST /v1/satisfaction          — บันทึกผลประเมิน
  GET  /v1/satisfaction/{id}     — ดูผลประเมินตาม id
  GET  /v1/satisfaction          — ดูผลประเมินทั้งหมดของ applicant_id (query param)
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.citizen_security import (
    CitizenClaims,
    get_owned_applicant,
    require_citizen,
)
from ...core.database import get_session
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
    claims: CitizenClaims = Depends(require_citizen),
) -> SatisfactionSurvey:
    await get_owned_applicant(session, body.applicant_id, claims)

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
    claims: CitizenClaims = Depends(require_citizen),
) -> list[SatisfactionSurvey]:
    await get_owned_applicant(session, applicant_id, claims)
    result = await session.execute(
        select(SatisfactionSurvey)
        .where(SatisfactionSurvey.applicant_id == applicant_id)
        .order_by(SatisfactionSurvey.created_at)
    )
    return list(result.scalars().all())
