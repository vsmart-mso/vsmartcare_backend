"""SLA กระบวนการพิจารณาคำร้อง — เริ่มนับจาก applicant-staff-fields เท่านั้น."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from ..constants.current_status import (
    CURRENT_STATUS_AID_COMPLETED,
    CURRENT_STATUS_WITHDRAWING,
)
from ..models.applicant import Applicant

_BANGKOK = ZoneInfo("Asia/Bangkok")

PROCESS_SLA_FREEZE_STATUS_IDS = frozenset({
    CURRENT_STATUS_AID_COMPLETED,  # 4
    CURRENT_STATUS_WITHDRAWING,  # 10
})

_ACRONYM_SOP = "สป"
_ACRONYM_DOY = "ดย"

TrafficColor = Literal["green", "yellow", "orange", "red"]


@dataclass(frozen=True)
class ProcessSlaDisplay:
    elapsed_days: int | None
    remaining_days: int | None
    traffic_color: TrafficColor | None
    is_overdue: bool | None


def normalize_money_acronym(value: str | None) -> str:
    """ตัดจุด/ช่องว่าง — เช่น \"สป.\" -> \"สป\"."""
    if not value:
        return ""
    return re.sub(r"[\s.]+", "", value.strip())


def resolve_process_sla_days(
    name_acronym: str | None,
    *,
    is_existing_case: bool = False,
    bank_code: str | None = None,  # noqa: ARG001 — คงพารามิเตอร์เดิม ไม่ใช้แล้ว
) -> int | None:
    """คืนจำนวนวัน SLA — สป.=7, ดย.=10, อื่น=10 (รายเดิม) หรือ 15 (รายใหม่)."""
    acronym = normalize_money_acronym(name_acronym)
    if not acronym:
        return None
    if acronym == _ACRONYM_SOP:
        return 7
    if acronym == _ACRONYM_DOY:
        return 10
    return 10 if is_existing_case else 15


def _traffic_color_fixed_sla(elapsed: int, sla_days: int) -> TrafficColor:
    if sla_days == 10:
        if elapsed <= 4:
            return "green"
        if elapsed <= 7:
            return "yellow"
        if elapsed <= 10:
            return "orange"
        return "red"
    # sla_days == 15
    if elapsed <= 5:
        return "green"
    if elapsed <= 11:
        return "yellow"
    if elapsed <= 15:
        return "orange"
    return "red"


def _traffic_color_proportional(elapsed: int, sla_days: int) -> TrafficColor:
    if sla_days <= 0:
        return "red"
    pct = elapsed / sla_days
    if pct <= 0.40:
        return "green"
    if pct <= 0.70:
        return "yellow"
    if pct <= 1.0:
        return "orange"
    return "red"


def traffic_color_for_elapsed(elapsed: int, sla_days: int) -> TrafficColor:
    if sla_days in (10, 15):
        return _traffic_color_fixed_sla(elapsed, sla_days)
    return _traffic_color_proportional(elapsed, sla_days)


def _now_bangkok(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(tz=_BANGKOK)
    if now.tzinfo is None:
        return now.replace(tzinfo=_BANGKOK)
    return now.astimezone(_BANGKOK)


def calendar_days_elapsed(started_at: datetime, *, now: datetime | None = None) -> int:
    """จำนวนวันปฏิทิน (Asia/Bangkok) ตั้งแต่เริ่มนับถึงวันนี้."""
    end = _now_bangkok(now)
    start = started_at.astimezone(_BANGKOK) if started_at.tzinfo else started_at.replace(tzinfo=_BANGKOK)
    return (end.date() - start.date()).days


def compute_process_display(
    started_at: datetime | None,
    sla_days: int | None,
    *,
    completed_at: datetime | None = None,
    frozen_elapsed: int | None = None,
    now: datetime | None = None,
) -> ProcessSlaDisplay:
    empty = ProcessSlaDisplay(
        elapsed_days=None,
        remaining_days=None,
        traffic_color=None,
        is_overdue=None,
    )
    if sla_days is None:
        return empty
    if started_at is None:
        if completed_at is not None and frozen_elapsed is not None:
            remaining = sla_days - frozen_elapsed
            return ProcessSlaDisplay(
                elapsed_days=frozen_elapsed,
                remaining_days=remaining,
                traffic_color=traffic_color_for_elapsed(frozen_elapsed, sla_days),
                is_overdue=remaining < 0,
            )
        return empty
    end = completed_at if completed_at is not None else now
    elapsed = calendar_days_elapsed(started_at, now=end)
    remaining = sla_days - elapsed
    return ProcessSlaDisplay(
        elapsed_days=elapsed,
        remaining_days=remaining,
        traffic_color=traffic_color_for_elapsed(elapsed, sla_days),
        is_overdue=remaining < 0,
    )


def freeze_process_sla_if_active(
    applicant: Applicant,
    *,
    now: datetime | None = None,
) -> bool:
    """หยุดนับ SLA — บันทึก snapshot ลง time_count_process และ process_completed_at."""
    if applicant.process_started_at is None or applicant.process_completed_at is not None:
        return False
    elapsed = calendar_days_elapsed(applicant.process_started_at, now=now)
    applicant.time_count_process = elapsed
    applicant.process_completed_at = _now_bangkok(now)
    return True


def maybe_freeze_process_sla_for_status(
    applicant: Applicant,
    new_status_id: int,
    *,
    now: datetime | None = None,
) -> bool:
    if new_status_id not in PROCESS_SLA_FREEZE_STATUS_IDS:
        return False
    return freeze_process_sla_if_active(applicant, now=now)


async def apply_process_sla_freeze_for_status_change(
    session: AsyncSession,
    *,
    applicant_id: int,
    new_status_id: int,
    now: datetime | None = None,
) -> None:
    if new_status_id not in PROCESS_SLA_FREEZE_STATUS_IDS:
        return
    applicant = await session.get(Applicant, applicant_id)
    if applicant is not None:
        maybe_freeze_process_sla_for_status(applicant, new_status_id, now=now)


def apply_process_sla_to_applicant(
    applicant: Applicant,
    *,
    category_acronym: str | None,
    bank_code: str | None,
    start_process: bool = False,
    recalc_sla_only: bool = False,
) -> None:
    sla_kwargs = {
        "is_existing_case": applicant.is_existing_case,
        "bank_code": bank_code,
    }
    if start_process:
        applicant.process_started_at = _now_bangkok()
        applicant.process_sla_days = resolve_process_sla_days(
            category_acronym,
            **sla_kwargs,
        )
        return
    if recalc_sla_only:
        acronym = normalize_money_acronym(category_acronym)
        if not acronym:
            applicant.process_sla_days = None
        else:
            applicant.process_sla_days = resolve_process_sla_days(
                category_acronym,
                **sla_kwargs,
            )


def process_sla_fields_dict(
    started_at: datetime | None,
    sla_days: int | None,
    *,
    completed_at: datetime | None = None,
    frozen_elapsed: int | None = None,
    now: datetime | None = None,
) -> dict[str, object]:
    """ฟิลด์ SLA สำหรับ merge เข้า response dict / Pydantic."""
    display = compute_process_display(
        started_at,
        sla_days,
        completed_at=completed_at,
        frozen_elapsed=frozen_elapsed,
        now=now,
    )
    return {
        "process_started_at": started_at,
        "process_completed_at": completed_at,
        "process_sla_days": sla_days,
        "process_elapsed_days": display.elapsed_days,
        "process_remaining_days": display.remaining_days,
        "process_traffic_color": display.traffic_color,
        "process_is_overdue": display.is_overdue,
        "time_count_process": display.elapsed_days,
    }


def is_sop_money_category(name_acronym: str | None) -> bool:
    """เงินอุดหนุนกรณีฉุกเฉิน (สป.)"""
    return normalize_money_acronym(name_acronym) == _ACRONYM_SOP


def apply_emergency_flag_for_money_category(
    applicant: Applicant,
    category_acronym: str | None,
) -> None:
    """ตั้ง is_emergency ตามหมวดเงิน — สป.=true, อื่น/ล้างหมวด=false."""
    applicant.is_emergency = is_sop_money_category(category_acronym)
