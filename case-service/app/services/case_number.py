"""สร้างเลขคำร้องรูปแบบ CASE-YYYYMM-000001 แบบรายเดือน (next index)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.applicant import Applicant

_BANGKOK = ZoneInfo("Asia/Bangkok")
_PREFIX = "CASE-"


def _month_key(reference: datetime | None = None) -> str:
    ref = reference.astimezone(_BANGKOK) if reference else datetime.now(_BANGKOK)
    return ref.strftime("%Y%m")


async def _next_monthly_index(session: AsyncSession, month_key: str) -> int:
    lock_key = int(month_key)
    await session.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": lock_key})

    prefix = f"{_PREFIX}{month_key}-"
    rows = await session.scalars(
        select(Applicant.case_number).where(
            Applicant.case_number.is_not(None),
            Applicant.case_number.ilike(f"{prefix}%"),
        )
    )

    max_index = 0
    for raw in rows:
        if raw is None:
            continue
        suffix = raw[len(prefix) :]
        if len(suffix) == 6 and suffix.isdigit():
            max_index = max(max_index, int(suffix))
    return max_index + 1


async def allocate_case_number(
    session: AsyncSession,
    *,
    reference: datetime | None = None,
) -> str:
    month_key = _month_key(reference)
    index = await _next_monthly_index(session, month_key)
    return f"{_PREFIX}{month_key}-{index:06d}"
