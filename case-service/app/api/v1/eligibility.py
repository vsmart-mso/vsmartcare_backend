"""บันทึกผลการคัดกรองเบื้องต้น (screening_logs) และความยินยอม (welfare_request_consents)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_session
from ...models.person import Person
from ...models.screening import ScreeningLog, WelfareRequestConsent
from ...schemas.screening import (
    ScreeningLogCreate,
    ScreeningLogRead,
    WelfareRequestConsentCreate,
    WelfareRequestConsentRead,
)

router = APIRouter(prefix="/v1", tags=["eligibility"])


async def _ensure_person_exists(session: AsyncSession, person_id: int) -> None:
    result = await session.execute(select(Person.id).where(Person.id == person_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="person_not_found")


@router.post(
    "/screening-logs",
    response_model=ScreeningLogRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_screening_log(
    body: ScreeningLogCreate,
    session: AsyncSession = Depends(get_session),
) -> ScreeningLogRead:
    await _ensure_person_exists(session, body.person_id)
    row = ScreeningLog(**body.model_dump())
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return ScreeningLogRead.model_validate(row)


@router.post(
    "/welfare-request-consents",
    response_model=WelfareRequestConsentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_welfare_request_consent(
    body: WelfareRequestConsentCreate,
    session: AsyncSession = Depends(get_session),
) -> WelfareRequestConsentRead:
    await _ensure_person_exists(session, body.person_id)
    row = WelfareRequestConsent(**body.model_dump())
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return WelfareRequestConsentRead.model_validate(row)
