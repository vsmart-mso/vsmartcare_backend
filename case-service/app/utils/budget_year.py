"""ปีงบประมาณไทย — 1 ตุลาคม ถึง 30 กันยายน (Asia/Bangkok)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

_BANGKOK = ZoneInfo("Asia/Bangkok")


def _to_bangkok(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=_BANGKOK)
    return dt.astimezone(_BANGKOK)


def thai_fiscal_year(reference: datetime) -> int:
    """คืนปีงบ พ.ศ. ที่ reference อยู่."""
    local = _to_bangkok(reference)
    if local.month >= 10:
        return local.year + 544
    return local.year + 543


def thai_fiscal_year_bounds(reference: datetime) -> tuple[datetime, datetime]:
    """คืน (start inclusive, end inclusive) ปีงบไทยที่ reference อยู่ — TZ Asia/Bangkok."""
    local = _to_bangkok(reference)
    start_year = local.year if local.month >= 10 else local.year - 1
    start = datetime(start_year, 10, 1, 0, 0, 0, tzinfo=_BANGKOK)
    end = datetime(start_year + 1, 9, 30, 23, 59, 59, 999999, tzinfo=_BANGKOK)
    return start, end


def is_same_thai_fiscal_year(a: datetime, b: datetime) -> bool:
    """True เมื่อ a และ b อยู่ในปีงบประมาณเดียวกัน."""
    return thai_fiscal_year(a) == thai_fiscal_year(b)
