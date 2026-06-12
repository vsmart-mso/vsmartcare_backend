"""ตรวจสถานะเปิด/ปิดบริการรายจังหวัด (TASK-v-care-12062026-01).

ใช้ที่ submit gate (`POST /v1/cases`) — แปลง person_id → จังหวัด ผ่าน geo hierarchy
แล้วอ่าน `province_access_config`. ไม่มี config / is_enabled=false = ปิด (default deny).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def is_province_enabled_by_person_id(session: AsyncSession, person_id: int) -> bool:
    """True = จังหวัดของ person เปิดรับบันทึกข้อมูล.

    เส้นทาง: persons → sub_districts_postcode → sub_districts → districts → province
             → LEFT JOIN province_access_config
    ถ้า person ไม่มี sub_district_postcode_id หรือไม่มี config → ปิด (default deny).
    """
    r = await session.execute(
        text(
            """
            SELECT COALESCE(pac.is_enabled, false)
            FROM persons p
            JOIN sub_districts_postcode sdp ON sdp.id = p.sub_district_postcode_id
            JOIN sub_districts sd ON sd.id = sdp.sub_district_id
            JOIN districts d ON d.id = sd.district_id
            LEFT JOIN province_access_config pac ON pac.province_id = d.province_id
            WHERE p.id = :pid
            LIMIT 1
            """
        ),
        {"pid": person_id},
    )
    row = r.first()
    return bool(row[0]) if row else False
