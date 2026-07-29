"""ยูทิลแปลงเวลาเป็นเขตเวลาไทย (Asia/Bangkok) สำหรับส่งออกทาง API.

ที่มา: คอลัมน์เวลาส่วนใหญ่ (เช่น Applicant.created_at) เป็น TIMESTAMP แบบไม่มี timezone
และค่ามาจาก func.now() บน Postgres ที่ตั้ง TZ = UTC → ค่าที่เก็บจึงเป็น "เวลา UTC แบบ naive".
ก่อนหน้านี้ API ส่งค่า naive นี้ออกไปตรงๆ ทำให้ทุกระบบแสดงเป็นเวลา UTC เสมือนเป็นเวลาไทย (คลาด 7 ชม.).
util นี้ถือว่า naive = UTC แล้วแปลงเป็นเวลาไทยแบบ aware (มี offset +07:00 ติดไปกับ ISO string).
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BANGKOK_TZ = ZoneInfo("Asia/Bangkok")


def to_bangkok(dt: datetime) -> datetime:
    """คืน datetime เวลาไทย (aware). ค่า naive ถือว่าเป็น UTC ตาม func.now() บน Postgres UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(BANGKOK_TZ)
