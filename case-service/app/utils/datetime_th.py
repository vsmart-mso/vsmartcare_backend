"""ยูทิลแปลงเวลาเป็นเขตเวลาไทย (Asia/Bangkok) สำหรับส่งออกทาง API.

ที่มา: คอลัมน์เวลาส่วนใหญ่ (เช่น Applicant.created_at) เป็น TIMESTAMP แบบไม่มี timezone
และค่ามาจาก func.now() บน Postgres ที่ตั้ง TZ = UTC → ค่าที่เก็บจึงเป็น "เวลา UTC แบบ naive".
ก่อนหน้านี้ API ส่งค่า naive นี้ออกไปตรงๆ ทำให้ทุกระบบแสดงเป็นเวลา UTC เสมือนเป็นเวลาไทย (คลาด 7 ชม.).
util นี้ถือว่า naive = UTC แล้วแปลงเป็นเวลาไทยแบบ aware (มี offset +07:00 ติดไปกับ ISO string).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

BANGKOK_TZ = ZoneInfo("Asia/Bangkok")

THAI_MONTH_ABBR: tuple[str, ...] = (
    "ม.ค.",
    "ก.พ.",
    "มี.ค.",
    "เม.ย.",
    "พ.ค.",
    "มิ.ย.",
    "ก.ค.",
    "ส.ค.",
    "ก.ย.",
    "ต.ค.",
    "พ.ย.",
    "ธ.ค.",
)


def to_bangkok(dt: datetime) -> datetime:
    """คืน datetime เวลาไทย (aware). ค่า naive ถือว่าเป็น UTC ตาม func.now() บน Postgres UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BANGKOK_TZ)


def format_thai_date(value: date | datetime | str | None) -> str | None:
    """แปลงวันที่เป็นข้อความไทย เช่น 5 ก.พ. 2569 (วัน เดือนย่อ ปี พ.ศ. = ค.ศ. + 543).

    datetime (เช่น created_at) ถือว่า naive = UTC แล้วเทียบวันตามเวลาไทยก่อนแปลงปี.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        value = to_bangkok(value)
    parsed = _as_date(value)
    if parsed is None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None
    return f"{parsed.day} {THAI_MONTH_ABBR[parsed.month - 1]} {parsed.year + 543}"


def _as_date(value: date | datetime | str) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None
