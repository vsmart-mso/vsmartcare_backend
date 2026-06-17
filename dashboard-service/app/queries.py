"""SQL ดิบสำหรับสรุปจำนวนคำร้อง (dashboard) — อ่านอย่างเดียวจาก DB ของ case-service

ใช้ raw SQL (`text()`) แทน ORM model เต็มรูปแบบ เพราะ service นี้แค่ "อ่าน" ตารางของ
case-service ไม่ได้เป็นเจ้าของ schema (เทียบ pattern เดียวกับที่
`case-service/app/services/province_access.py` ใช้สำหรับอ่านข้าม concern)

ตรรกะหา "จังหวัด/อำเภอ/ตำบล" ของ applicant 1 คน อ้างจาก
`case-service/app/api/v1/case_for_staff.py::primary_address_sq` ทุกตัวอักษร —
ใช้ที่อยู่แถวแรก (`address` เรียงตาม id) ถ้ามี ไม่งั้น fallback ไป `persons.sub_district_postcode_id`
เพื่อให้ตัวเลขในแดชบอร์ดตรงกับหน้ารายการเคสของเจ้าหน้าที่ (`GET /v1/case_for_staff`)

หมายเหตุ: ใช้ INNER JOIN ไปที่ตำแหน่งภูมิศาสตร์เหมือนต้นทาง — applicant ที่หาตำแหน่งไม่ได้เลย
(ไม่มีทั้ง address และ persons.sub_district_postcode_id) จะไม่ถูกนับ เหมือนพฤติกรรมของ
`/v1/case_for_staff` ปัจจุบัน
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# CTE กลาง: applicant ทุกคนของจังหวัดที่ขอ + district + current_status ล่าสุด
# (ใช้ `CAST(:param AS int[])` แทน shorthand `:param::int[]` — SQLAlchemy text() ไม่จับ
#  bind param ที่ตามด้วย "::" ทันที (regex กัน false-positive กับ cast operator ของ Postgres)
#  CAST(...) ทำให้ Postgres รู้ type ตอน prepare แม้ค่าที่ส่งมาเป็น NULL จึงไม่ต้องประกาศ
#  bindparam type แยก — ส่ง python list ตรง ๆ ใช้ได้กับ asyncpg)
_FILTERED_APPLICANTS_CTE = """
filtered_applicants AS (
    SELECT
        ap.id AS applicant_id,
        ap.type_money_category_id,
        d.id AS district_id,
        d.name AS district_name,
        ls.current_status_id AS current_status_id
    FROM applicants ap
    JOIN persons p ON p.id = ap.persons_id
    LEFT JOIN LATERAL (
        SELECT a.sub_district_postcode_id
        FROM address a
        WHERE a.applicant_id = ap.id
        ORDER BY a.id ASC
        LIMIT 1
    ) pa ON TRUE
    JOIN sub_districts_postcode sdp
        ON sdp.id = COALESCE(pa.sub_district_postcode_id, p.sub_district_postcode_id)
    JOIN sub_districts sd ON sd.id = sdp.sub_district_id
    JOIN districts d ON d.id = sd.district_id
    LEFT JOIN LATERAL (
        SELECT wrs.current_status_id
        FROM welfare_request_status wrs
        WHERE wrs.applicant_id = ap.id
        ORDER BY wrs.updated_at DESC, wrs.id DESC
        LIMIT 1
    ) ls ON TRUE
    WHERE d.province_id = :province_id
      AND (
          CAST(:type_money_ids AS int[]) IS NULL
          OR ap.type_money_category_id = ANY(CAST(:type_money_ids AS int[]))
      )
)
"""


# CTE ระดับประเทศ: เหมือน _FILTERED_APPLICANTS_CTE แต่ไม่กรองจังหวัด + เพิ่ม province_id ใน SELECT
_NATIONAL_FILTERED_APPLICANTS_CTE = """
national_filtered AS (
    SELECT
        ap.id AS applicant_id,
        ap.type_money_category_id,
        d.province_id AS province_id,
        ls.current_status_id AS current_status_id
    FROM applicants ap
    JOIN persons p ON p.id = ap.persons_id
    LEFT JOIN LATERAL (
        SELECT a.sub_district_postcode_id
        FROM address a
        WHERE a.applicant_id = ap.id
        ORDER BY a.id ASC
        LIMIT 1
    ) pa ON TRUE
    JOIN sub_districts_postcode sdp
        ON sdp.id = COALESCE(pa.sub_district_postcode_id, p.sub_district_postcode_id)
    JOIN sub_districts sd ON sd.id = sdp.sub_district_id
    JOIN districts d ON d.id = sd.district_id
    LEFT JOIN LATERAL (
        SELECT wrs.current_status_id
        FROM welfare_request_status wrs
        WHERE wrs.applicant_id = ap.id
        ORDER BY wrs.updated_at DESC, wrs.id DESC
        LIMIT 1
    ) ls ON TRUE
    WHERE (
        CAST(:type_money_ids AS int[]) IS NULL
        OR ap.type_money_category_id = ANY(CAST(:type_money_ids AS int[]))
    )
)
"""


async def fetch_national_total(
    session: AsyncSession,
    *,
    type_money_ids: list[int] | None,
) -> int:
    sql = text(
        f"WITH {_NATIONAL_FILTERED_APPLICANTS_CTE} SELECT COUNT(*) FROM national_filtered"
    )
    return await session.scalar(sql, {"type_money_ids": type_money_ids}) or 0


async def fetch_national_status_counts(
    session: AsyncSession,
    *,
    type_money_ids: list[int] | None,
) -> list[dict]:
    sql = text(
        f"""
        WITH {_NATIONAL_FILTERED_APPLICANTS_CTE}
        SELECT
            cs.id AS current_status_id,
            cs.description_staff AS label,
            cs.color AS color,
            COUNT(fa.applicant_id) AS count
        FROM current_status cs
        LEFT JOIN national_filtered fa ON fa.current_status_id = cs.id
        WHERE cs.filter_activate = true
        GROUP BY cs.id, cs.description_staff, cs.color, cs.filter_order
        ORDER BY cs.filter_order
        """
    )
    rows = (await session.execute(sql, {"type_money_ids": type_money_ids})).mappings().all()
    return [dict(r) for r in rows]


async def fetch_provinces_total_count(session: AsyncSession) -> int:
    return await session.scalar(text("SELECT COUNT(*) FROM province")) or 0


async def fetch_provinces_page(
    session: AsyncSession,
    *,
    current_status_ids: list[int] | None,
    type_money_ids: list[int] | None,
    limit: int,
    offset: int,
) -> list[dict]:
    sql = text(
        f"""
        WITH {_NATIONAL_FILTERED_APPLICANTS_CTE}
        SELECT
            prov.id AS province_id,
            prov.name AS province_name,
            COUNT(fa.applicant_id) FILTER (
                WHERE cs.filter_activate = true
                  AND (
                      CAST(:current_status_ids AS int[]) IS NULL
                      OR fa.current_status_id = ANY(CAST(:current_status_ids AS int[]))
                  )
            ) AS total
        FROM province prov
        LEFT JOIN national_filtered fa ON fa.province_id = prov.id
        LEFT JOIN current_status cs ON cs.id = fa.current_status_id
        GROUP BY prov.id, prov.name
        ORDER BY prov.id
        LIMIT :limit OFFSET :offset
        """
    )
    rows = (
        await session.execute(
            sql,
            {
                "type_money_ids": type_money_ids,
                "current_status_ids": current_status_ids,
                "limit": limit,
                "offset": offset,
            },
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def fetch_provinces_status_breakdown(
    session: AsyncSession,
    *,
    province_ids: list[int],
    current_status_ids: list[int] | None,
    type_money_ids: list[int] | None,
) -> list[dict]:
    if not province_ids:
        return []
    sql = text(
        f"""
        WITH {_NATIONAL_FILTERED_APPLICANTS_CTE}
        SELECT
            prov.id AS province_id,
            cs.id AS current_status_id,
            COUNT(fa.applicant_id) AS count
        FROM province prov
        CROSS JOIN current_status cs
        LEFT JOIN national_filtered fa
            ON fa.province_id = prov.id AND fa.current_status_id = cs.id
        WHERE prov.id = ANY(CAST(:province_ids AS int[]))
          AND cs.filter_activate = true
          AND (
              CAST(:current_status_ids AS int[]) IS NULL
              OR cs.id = ANY(CAST(:current_status_ids AS int[]))
          )
        GROUP BY prov.id, cs.id
        """
    )
    rows = (
        await session.execute(
            sql,
            {
                "type_money_ids": type_money_ids,
                "province_ids": province_ids,
                "current_status_ids": current_status_ids,
            },
        )
    ).mappings().all()
    return [dict(r) for r in rows]


_DISTRICT_FILTERED_APPLICANTS_CTE = """
district_filtered AS (
    SELECT
        ap.id AS applicant_id,
        ap.type_money_category_id,
        sd.id AS sub_district_id,
        sd.name AS sub_district_name,
        ls.current_status_id AS current_status_id
    FROM applicants ap
    JOIN persons p ON p.id = ap.persons_id
    LEFT JOIN LATERAL (
        SELECT a.sub_district_postcode_id
        FROM address a
        WHERE a.applicant_id = ap.id
        ORDER BY a.id ASC
        LIMIT 1
    ) pa ON TRUE
    JOIN sub_districts_postcode sdp
        ON sdp.id = COALESCE(pa.sub_district_postcode_id, p.sub_district_postcode_id)
    JOIN sub_districts sd ON sd.id = sdp.sub_district_id
    JOIN districts d ON d.id = sd.district_id
    LEFT JOIN LATERAL (
        SELECT wrs.current_status_id
        FROM welfare_request_status wrs
        WHERE wrs.applicant_id = ap.id
        ORDER BY wrs.updated_at DESC, wrs.id DESC
        LIMIT 1
    ) ls ON TRUE
    WHERE d.id = :district_id
      AND d.province_id = :province_id
      AND (
          CAST(:type_money_ids AS int[]) IS NULL
          OR ap.type_money_category_id = ANY(CAST(:type_money_ids AS int[]))
      )
)
"""


async def fetch_district(
    session: AsyncSession, district_id: int, province_id: int
) -> dict | None:
    row = (
        await session.execute(
            text(
                """
                SELECT d.id AS district_id, d.name AS district_name,
                       p.id AS province_id, p.name AS province_name
                FROM districts d
                JOIN province p ON p.id = d.province_id
                WHERE d.id = :district_id AND d.province_id = :province_id
                """
            ),
            {"district_id": district_id, "province_id": province_id},
        )
    ).mappings().first()
    return dict(row) if row else None


async def fetch_sub_districts_total_count(
    session: AsyncSession, *, district_id: int
) -> int:
    return (
        await session.scalar(
            text("SELECT COUNT(*) FROM sub_districts WHERE district_id = :district_id"),
            {"district_id": district_id},
        )
        or 0
    )


async def fetch_sub_districts_page(
    session: AsyncSession,
    *,
    district_id: int,
    province_id: int,
    current_status_ids: list[int] | None,
    type_money_ids: list[int] | None,
    limit: int,
    offset: int,
) -> list[dict]:
    sql = text(
        f"""
        WITH {_DISTRICT_FILTERED_APPLICANTS_CTE}
        SELECT
            sd.id AS sub_district_id,
            sd.name AS sub_district_name,
            COUNT(df.applicant_id) FILTER (
                WHERE cs.filter_activate = true
                  AND (
                      CAST(:current_status_ids AS int[]) IS NULL
                      OR df.current_status_id = ANY(CAST(:current_status_ids AS int[]))
                  )
            ) AS total
        FROM sub_districts sd
        LEFT JOIN district_filtered df ON df.sub_district_id = sd.id
        LEFT JOIN current_status cs ON cs.id = df.current_status_id
        WHERE sd.district_id = :district_id
        GROUP BY sd.id, sd.name
        ORDER BY sd.id
        LIMIT :limit OFFSET :offset
        """
    )
    rows = (
        await session.execute(
            sql,
            {
                "district_id": district_id,
                "province_id": province_id,
                "type_money_ids": type_money_ids,
                "current_status_ids": current_status_ids,
                "limit": limit,
                "offset": offset,
            },
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def fetch_sub_districts_status_breakdown(
    session: AsyncSession,
    *,
    district_id: int,
    province_id: int,
    sub_district_ids: list[int],
    current_status_ids: list[int] | None,
    type_money_ids: list[int] | None,
) -> list[dict]:
    if not sub_district_ids:
        return []
    sql = text(
        f"""
        WITH {_DISTRICT_FILTERED_APPLICANTS_CTE}
        SELECT
            sd.id AS sub_district_id,
            cs.id AS current_status_id,
            COUNT(df.applicant_id) AS count
        FROM sub_districts sd
        CROSS JOIN current_status cs
        LEFT JOIN district_filtered df
            ON df.sub_district_id = sd.id AND df.current_status_id = cs.id
        WHERE sd.id = ANY(CAST(:sub_district_ids AS int[]))
          AND cs.filter_activate = true
          AND (
              CAST(:current_status_ids AS int[]) IS NULL
              OR cs.id = ANY(CAST(:current_status_ids AS int[]))
          )
        GROUP BY sd.id, cs.id
        """
    )
    rows = (
        await session.execute(
            sql,
            {
                "district_id": district_id,
                "province_id": province_id,
                "type_money_ids": type_money_ids,
                "sub_district_ids": sub_district_ids,
                "current_status_ids": current_status_ids,
            },
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def fetch_province(session: AsyncSession, province_id: int) -> dict | None:
    row = (
        await session.execute(
            text("SELECT id, name FROM province WHERE id = :province_id"),
            {"province_id": province_id},
        )
    ).mappings().first()
    return dict(row) if row else None


async def fetch_overview_total(
    session: AsyncSession,
    *,
    province_id: int,
    type_money_ids: list[int] | None,
) -> int:
    """จำนวน applicant ทั้งหมดที่ตรง filter (ไม่ผูกกับ current_status.filter_activate)."""
    sql = text(f"WITH {_FILTERED_APPLICANTS_CTE} SELECT COUNT(*) FROM filtered_applicants")
    return (
        await session.scalar(
            sql,
            {"province_id": province_id, "type_money_ids": type_money_ids},
        )
        or 0
    )


async def fetch_overview_status_counts(
    session: AsyncSession,
    *,
    province_id: int,
    type_money_ids: list[int] | None,
) -> list[dict]:
    """นับจำนวนต่อ current_status (เฉพาะสถานะที่ filter_activate=true) — ใช้ทำ donut chart."""
    sql = text(
        f"""
        WITH {_FILTERED_APPLICANTS_CTE}
        SELECT
            cs.id AS current_status_id,
            cs.description_staff AS label,
            cs.color AS color,
            COUNT(fa.applicant_id) AS count
        FROM current_status cs
        LEFT JOIN filtered_applicants fa ON fa.current_status_id = cs.id
        WHERE cs.filter_activate = true
        GROUP BY cs.id, cs.description_staff, cs.color, cs.filter_order
        ORDER BY cs.filter_order
        """
    )
    rows = (
        await session.execute(
            sql,
            {"province_id": province_id, "type_money_ids": type_money_ids},
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def fetch_active_current_statuses(session: AsyncSession) -> list[dict]:
    """label/สี ของทุก current_status ที่ filter_activate=true — ใช้ตั้งชื่อคอลัมน์ตอน export Excel."""
    rows = (
        await session.execute(
            text(
                """
                SELECT id, description_staff AS label, color
                FROM current_status
                WHERE filter_activate = true
                ORDER BY filter_order
                """
            )
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def fetch_districts_total_count(session: AsyncSession, *, province_id: int) -> int:
    return (
        await session.scalar(
            text("SELECT COUNT(*) FROM districts WHERE province_id = :province_id"),
            {"province_id": province_id},
        )
        or 0
    )


async def fetch_districts_page(
    session: AsyncSession,
    *,
    province_id: int,
    current_status_ids: list[int] | None,
    type_money_ids: list[int] | None,
    limit: int,
    offset: int,
) -> list[dict]:
    """หน้าปัจจุบันของรายอำเภอ (ทุกอำเภอในจังหวัด แม้ไม่มีคำร้องเลย) + total ที่ผ่าน filter."""
    sql = text(
        f"""
        WITH {_FILTERED_APPLICANTS_CTE}
        SELECT
            d.id AS district_id,
            d.name AS district_name,
            COUNT(fa.applicant_id) FILTER (
                WHERE cs.filter_activate = true
                  AND (
                      CAST(:current_status_ids AS int[]) IS NULL
                      OR fa.current_status_id = ANY(CAST(:current_status_ids AS int[]))
                  )
            ) AS total
        FROM districts d
        LEFT JOIN filtered_applicants fa ON fa.district_id = d.id
        LEFT JOIN current_status cs ON cs.id = fa.current_status_id
        WHERE d.province_id = :province_id
        GROUP BY d.id, d.name
        ORDER BY d.id
        LIMIT :limit OFFSET :offset
        """
    )
    rows = (
        await session.execute(
            sql,
            {
                "province_id": province_id,
                "type_money_ids": type_money_ids,
                "current_status_ids": current_status_ids,
                "limit": limit,
                "offset": offset,
            },
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def fetch_districts_status_breakdown(
    session: AsyncSession,
    *,
    province_id: int,
    district_ids: list[int],
    current_status_ids: list[int] | None,
    type_money_ids: list[int] | None,
) -> list[dict]:
    """นับต่อ (district_id, current_status_id) สำหรับอำเภอที่อยู่ในหน้านี้เท่านั้น

    คืนแถวครบทุก (district × current_status ที่ filter_activate=true) แม้ count=0
    เพื่อให้ฝั่ง caller pivot เป็นคอลัมน์ได้ตรงกันทุกแถว
    """
    if not district_ids:
        return []
    sql = text(
        f"""
        WITH {_FILTERED_APPLICANTS_CTE}
        SELECT
            d.id AS district_id,
            cs.id AS current_status_id,
            COUNT(fa.applicant_id) AS count
        FROM districts d
        CROSS JOIN current_status cs
        LEFT JOIN filtered_applicants fa
            ON fa.district_id = d.id AND fa.current_status_id = cs.id
        WHERE d.id = ANY(CAST(:district_ids AS int[]))
          AND cs.filter_activate = true
          AND (
              CAST(:current_status_ids AS int[]) IS NULL
              OR cs.id = ANY(CAST(:current_status_ids AS int[]))
          )
        GROUP BY d.id, cs.id
        """
    )
    rows = (
        await session.execute(
            sql,
            {
                "province_id": province_id,
                "type_money_ids": type_money_ids,
                "district_ids": district_ids,
                "current_status_ids": current_status_ids,
            },
        )
    ).mappings().all()
    return [dict(r) for r in rows]
