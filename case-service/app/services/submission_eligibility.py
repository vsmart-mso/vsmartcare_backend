"""ตรวจสอบสิทธิ์ยื่นคำขอและเข้าพอร์ทัลประชาชน — cooldown 30 วันปฏิทิน."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants.current_status import (
    ACTIVE_CASE_STATUS_IDS,
    COOLDOWN_DAYS,
    COOLDOWN_STATUS_IDS,
)
from ..models.applicant import Applicant
from ..schemas.submission_eligibility import SubmissionEligibilityRead
from .citizen_status_email_policy import fetch_latest_status_id

_BANGKOK = ZoneInfo("Asia/Bangkok")

EligibilityReason = Literal["none", "active_case", "cooldown", "eligible", "unknown_status"]


@dataclass(frozen=True)
class SubmissionEligibilityResult:
    can_submit: bool
    can_access_portal: bool
    reason: EligibilityReason
    last_applicant_id: int | None
    last_submitted_at: datetime | None
    eligible_at: datetime | None
    days_remaining: int | None
    current_status_id: int | None

    def to_read(self) -> SubmissionEligibilityRead:
        return SubmissionEligibilityRead(
            can_submit=self.can_submit,
            can_access_portal=self.can_access_portal,
            reason=self.reason,
            last_applicant_id=self.last_applicant_id,
            last_submitted_at=self.last_submitted_at,
            eligible_at=self.eligible_at,
            days_remaining=self.days_remaining,
            current_status_id=self.current_status_id,
        )


def _to_bangkok(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_BANGKOK)
    return dt.astimezone(_BANGKOK)


def compute_eligible_at(submitted_at: datetime) -> datetime:
    """วันที่ยื่นคำขอครั้งถัดไปได้ — นับ 30 วันปฏิทินจากวันส่งสำเร็จ."""
    return _to_bangkok(submitted_at) + timedelta(days=COOLDOWN_DAYS)


def compute_days_remaining(eligible_at: datetime, now: datetime) -> int:
    """จำนวนวันที่เหลือก่อนยื่นได้ (ปัดขึ้น)."""
    delta = _to_bangkok(eligible_at) - _to_bangkok(now)
    if delta.total_seconds() <= 0:
        return 0
    return math.ceil(delta.total_seconds() / 86400)


def evaluate_submission_eligibility(
    *,
    last_applicant_id: int | None,
    last_submitted_at: datetime | None,
    current_status_id: int | None,
    now: datetime | None = None,
) -> SubmissionEligibilityResult:
    """คำนวณสิทธิ์จากคำขอล่าสุด — ใช้ใน service."""
    if last_applicant_id is None or last_submitted_at is None:
        return SubmissionEligibilityResult(
            can_submit=True,
            can_access_portal=True,
            reason="none",
            last_applicant_id=None,
            last_submitted_at=None,
            eligible_at=None,
            days_remaining=None,
            current_status_id=None,
        )

    reference_now = _to_bangkok(now or datetime.now(_BANGKOK))

    if current_status_id in ACTIVE_CASE_STATUS_IDS:
        return SubmissionEligibilityResult(
            can_submit=False,
            can_access_portal=True,
            reason="active_case",
            last_applicant_id=last_applicant_id,
            last_submitted_at=last_submitted_at,
            eligible_at=None,
            days_remaining=None,
            current_status_id=current_status_id,
        )

    if current_status_id in COOLDOWN_STATUS_IDS:
        eligible_at = compute_eligible_at(last_submitted_at)
        if reference_now >= _to_bangkok(eligible_at):
            return SubmissionEligibilityResult(
                can_submit=True,
                can_access_portal=True,
                reason="eligible",
                last_applicant_id=last_applicant_id,
                last_submitted_at=last_submitted_at,
                eligible_at=eligible_at,
                days_remaining=None,
                current_status_id=current_status_id,
            )
        return SubmissionEligibilityResult(
            can_submit=False,
            can_access_portal=True,
            reason="cooldown",
            last_applicant_id=last_applicant_id,
            last_submitted_at=last_submitted_at,
            eligible_at=eligible_at,
            days_remaining=compute_days_remaining(eligible_at, reference_now),
            current_status_id=current_status_id,
        )

    return SubmissionEligibilityResult(
        can_submit=False,
        can_access_portal=True,
        reason="unknown_status",
        last_applicant_id=last_applicant_id,
        last_submitted_at=last_submitted_at,
        eligible_at=None,
        days_remaining=None,
        current_status_id=current_status_id,
    )


async def _fetch_latest_applicant(
    session: AsyncSession,
    *,
    persons_id: int,
) -> Applicant | None:
    return await session.scalar(
        select(Applicant)
        .where(Applicant.persons_id == persons_id)
        .order_by(Applicant.created_at.desc(), Applicant.id.desc())
        .limit(1),
    )


async def resolve_submission_eligibility(
    session: AsyncSession,
    *,
    persons_id: int,
    now: datetime | None = None,
) -> SubmissionEligibilityResult:
    """ดึงคำขอล่าสุดของบุคคลแล้วประเมินสิทธิ์."""
    latest = await _fetch_latest_applicant(session, persons_id=persons_id)
    if latest is None:
        return evaluate_submission_eligibility(
            last_applicant_id=None,
            last_submitted_at=None,
            current_status_id=None,
            now=now,
        )

    current_status_id = await fetch_latest_status_id(session, applicant_id=latest.id)
    return evaluate_submission_eligibility(
        last_applicant_id=latest.id,
        last_submitted_at=latest.created_at,
        current_status_id=current_status_id,
        now=now,
    )


def conflict_detail_for_reason(reason: EligibilityReason) -> str:
    """HTTP 409 detail สำหรับ POST /v1/cases เมื่อ can_submit เป็น false."""
    if reason == "active_case":
        return "active_case_exists"
    if reason == "cooldown":
        return "submission_cooldown_active"
    return "submission_not_allowed"
