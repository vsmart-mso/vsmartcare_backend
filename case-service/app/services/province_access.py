"""ตรวจสถานะเปิด/ปิดบริการรายจังหวัด (TASK-v-care-12062026-01).

ใช้ที่ submit gate (`POST /v1/cases`, `PATCH /v1/cases/{id}`) — อ่าน `persons.province_id` ตรง ๆ
(resolve ไว้แล้วตอน login จากที่อยู่ ThaiD โดย thaid-auth-service — ดู
thaid-auth-service/app/person_persist.py::resolve_province_id_from_address) แล้วอ่าน
`province_access_config` เพื่อให้ gate นี้กับ gate ตอน login อ่านค่าจังหวัดเดียวกันเป๊ะ ไม่มีทาง drift
กันอีก (เดิมเดินผ่าน sub_district_postcode_id → sub_district → district → province ซึ่งพังเมื่อ
resolve ตอน login ไม่สำเร็จ เช่น กรุงเทพฯ/เมืองพัทยา ทำให้ user login ผ่านแต่โดนบล็อกตอน submit)

person ที่ resolve จังหวัดไม่ได้ (province_id เป็น NULL) → fail-open (เหมือน login) ไม่บล็อก
ไม่มี config ของจังหวัดนั้นเลย / is_enabled=false → ปิด (default deny)
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def is_province_enabled_by_person_id(session: AsyncSession, person_id: int) -> bool:
    """True = จังหวัดของ person เปิดรับบันทึกข้อมูล (หรือ resolve จังหวัดไม่ได้ → fail-open)."""
    r = await session.execute(
        text(
            """
            SELECT p.province_id, pac.is_enabled
            FROM persons p
            LEFT JOIN province_access_config pac ON pac.province_id = p.province_id
            WHERE p.id = :pid
            LIMIT 1
            """
        ),
        {"pid": person_id},
    )
    row = r.first()
    if row is None:
        return False
    province_id, is_enabled = row
    if province_id is None:
        return True
    return bool(is_enabled)
