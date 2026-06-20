"""บันทึกผลการคัดกรองเบื้องต้น (screening_logs) และความยินยอม (welfare_request_consents)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.citizen_security import (
    CitizenClaims,
    assert_person_owner,
    require_citizen,
)
from ...core.database import get_session
from ...models.screening import ScreeningLog, WelfareRequestConsent
from ...schemas.screening import (
    ScreeningLogCreate,
    ScreeningLogRead,
    WelfareRequestConsentCreate,
    WelfareRequestConsentRead,
)

router = APIRouter(prefix="/v1", tags=["eligibility"])


@router.get("/screening-logs/latest-passed", response_model=ScreeningLogRead | None)
async def get_latest_passed_screening_log(
    person_id: int = Query(..., description="ID ของ person"),
    session: AsyncSession = Depends(get_session),
    claims: CitizenClaims = Depends(require_citizen),
) -> ScreeningLogRead | None:
    """คืน screening log ล่าสุดที่ผ่านเกณฑ์ (screening_status=true) หรือ null ถ้าไม่มี."""
    assert_person_owner(person_id, claims)
    stmt = (
        select(ScreeningLog)
        .where(ScreeningLog.person_id == person_id)
        .where(ScreeningLog.screening_status == True)  # noqa: E712
        .order_by(ScreeningLog.id.desc())
        .limit(1)
    )
    r = await session.execute(stmt)
    row = r.scalar_one_or_none()
    if row is None:
        return None
    return ScreeningLogRead.model_validate(row)


@router.post(
    "/screening-logs",
    response_model=ScreeningLogRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_screening_log(
    body: ScreeningLogCreate,
    session: AsyncSession = Depends(get_session),
    claims: CitizenClaims = Depends(require_citizen),
) -> ScreeningLogRead:
    assert_person_owner(body.person_id, claims)
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
    claims: CitizenClaims = Depends(require_citizen),
) -> WelfareRequestConsentRead:
    assert_person_owner(body.person_id, claims)
    row = WelfareRequestConsent(**body.model_dump())
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return WelfareRequestConsentRead.model_validate(row)
