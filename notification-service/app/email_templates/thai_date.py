"""แปลงวันที่ ISO เป็นข้อความไทยสำหรับอีเมล — เช่น วันที่ 23 พฤษภาคม 2569."""

from __future__ import annotations

from datetime import date, datetime

_BUDDHIST_ERA_OFFSET = 543

_THAI_MONTHS: tuple[str, ...] = (
    "มกราคม",
    "กุมภาพันธ์",
    "มีนาคม",
    "เมษายน",
    "พฤษภาคม",
    "มิถุนายน",
    "กรกฎาคม",
    "สิงหาคม",
    "กันยายน",
    "ตุลาคม",
    "พฤศจิกายน",
    "ธันวาคม",
)


def _parse_date(value: str | date | datetime | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    iso_part = raw.split("T", 1)[0][:10]
    try:
        return date.fromisoformat(iso_part)
    except ValueError:
        return None


def format_thai_date(value: str | date | datetime | None) -> str:
    """คืน 'วันที่ 23 พฤษภาคม 2569' จาก ISO หรือ date object."""
    parsed = _parse_date(value)
    if parsed is None:
        return str(value).strip() if value else ""
    be_year = parsed.year + _BUDDHIST_ERA_OFFSET
    month_name = _THAI_MONTHS[parsed.month - 1]
    return f"วันที่ {parsed.day} {month_name} {be_year}"


def format_thai_date_dmy(value: str | date | datetime | None) -> str:
    """คงชื่อเดิมเพื่อ backward compat — ใช้รูปแบบชื่อเดือนเต็ม."""
    return format_thai_date(value)
