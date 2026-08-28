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

from dataclasses import dataclass
from datetime import date

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


# CTE ระดับประเทศ: เหมือน _FILTERED_APPLICANTS_CTE แต่กรองจังหวัดได้หลายค่า (ไม่ส่ง = ทุกจังหวัด)
# + เพิ่ม province_id ใน SELECT
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
      AND (
        CAST(:province_ids AS int[]) IS NULL
        OR d.province_id = ANY(CAST(:province_ids AS int[]))
    )
)
"""


async def fetch_national_total(
    session: AsyncSession,
    *,
    province_ids: list[int] | None,
    current_status_ids: list[int] | None,
    type_money_ids: list[int] | None,
) -> int:
    # นับเฉพาะ applicant ที่มีสถานะซึ่งยัง filter_activate อยู่ ให้ฐานของ percent ตรงกับ
    # ผลรวมของ statuses[].count (ซึ่ง join current_status ที่ filter_activate = true)
    sql = text(
        f"""
        WITH {_NATIONAL_FILTERED_APPLICANTS_CTE}
        SELECT COUNT(fa.applicant_id)
        FROM national_filtered fa
        JOIN current_status cs ON cs.id = fa.current_status_id
        WHERE cs.filter_activate = true
          AND (
              CAST(:current_status_ids AS int[]) IS NULL
              OR fa.current_status_id = ANY(CAST(:current_status_ids AS int[]))
          )
        """
    )
    return (
        await session.scalar(
            sql,
            {
                "province_ids": province_ids,
                "current_status_ids": current_status_ids,
                "type_money_ids": type_money_ids,
            },
        )
        or 0
    )


async def fetch_national_status_counts(
    session: AsyncSession,
    *,
    province_ids: list[int] | None,
    current_status_ids: list[int] | None,
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
          AND (
              CAST(:current_status_ids AS int[]) IS NULL
              OR cs.id = ANY(CAST(:current_status_ids AS int[]))
          )
        GROUP BY cs.id, cs.description_staff, cs.color, cs.filter_order
        ORDER BY cs.filter_order
        """
    )
    rows = (
        await session.execute(
            sql,
            {
                "province_ids": province_ids,
                "current_status_ids": current_status_ids,
                "type_money_ids": type_money_ids,
            },
        )
    ).mappings().all()
    return [dict(r) for r in rows]


async def fetch_provinces_total_count(
    session: AsyncSession,
    *,
    province_ids: list[int] | None = None,
) -> int:
    sql = text(
        """
        SELECT COUNT(*) FROM province
        WHERE (
            CAST(:province_ids AS int[]) IS NULL
            OR id = ANY(CAST(:province_ids AS int[]))
        )
        """
    )
    return await session.scalar(sql, {"province_ids": province_ids}) or 0


async def fetch_existing_province_ids(session: AsyncSession, province_ids: list[int]) -> set[int]:
    """คืนเฉพาะ id ที่มีจริงใน `province` — ใช้หาว่าค่าไหนผิดเพื่อบอกใน error 404."""
    if not province_ids:
        return set()
    sql = text("SELECT id FROM province WHERE id = ANY(CAST(:province_ids AS int[]))")
    rows = (await session.execute(sql, {"province_ids": province_ids})).scalars().all()
    return set(rows)


async def fetch_provinces_page(
    session: AsyncSession,
    *,
    province_ids: list[int] | None,
    current_status_ids: list[int] | None,
    type_money_ids: list[int] | None,
    limit: int,
    offset: int,
) -> list[dict]:
    # กรอง prov ที่ outer query ด้วย ไม่ใช่แค่ใน CTE — ไม่งั้นจังหวัดนอก filter ยังโผล่มา
    # เป็นแถว total = 0 (เพราะ LEFT JOIN) และ pagination จะนับจากทั้ง 77 จังหวัดเหมือนเดิม
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
        WHERE (
            CAST(:province_ids AS int[]) IS NULL
            OR prov.id = ANY(CAST(:province_ids AS int[]))
        )
        GROUP BY prov.id, prov.name
        ORDER BY prov.id
        LIMIT :limit OFFSET :offset
        """
    )
    rows = (
        await session.execute(
            sql,
            {
                "province_ids": province_ids,
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
    # `:province_ids` ถูกใช้ทั้งใน CTE และ outer WHERE โดยตั้งใจ — ค่าที่ส่งมาคือจังหวัดของ
    # หน้าปัจจุบัน ซึ่งเป็น subset ของ province filter อยู่แล้ว การกรองใน CTE ด้วยจึงถูกต้อง
    # และช่วยตัดงานตั้งแต่ต้นทาง
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
            sd.code AS sub_district_code,
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
        GROUP BY sd.id, sd.code, sd.name
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
            d.code AS district_code,
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
        GROUP BY d.id, d.code, d.name
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


# ---------------------------------------------------------------------------
# รายการคำร้อง (คัดจาก case_for_staff list) — province_id ไม่บังคับ = ทั้งประเทศ
# ---------------------------------------------------------------------------

CURRENT_STATUS_PENDING_INTAKE = 1
CURRENT_STATUS_EDIT_REQUESTED = 8
ATTACHMENT_TYPE_KTB_CORPORATE = 11
DISABILITY_RECEIVED_WELFARE_TYPE_IDS = (4, 11)


@dataclass(frozen=True)
class DashboardCaseFilters:
    province_ids: list[int] | None = None
    current_status_ids: list[int] | None = None
    type_money_ids: list[int] | None = None
    case_number: str | None = None
    current_status: str | None = None
    firstname: str | None = None
    lastname: str | None = None
    cid: str | None = None
    datetime_create: date | None = None
    province_name: str | None = None
    district_id: int | None = None
    district_name: str | None = None
    subdistrict_id: int | None = None
    subdistrict_name: str | None = None
    subdistrict_postcode_id: int | None = None
    postcode: str | None = None


_CASES_LOCATION_FROM = """
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
JOIN province prov ON prov.id = d.province_id
JOIN postcode pc ON pc.id = sdp.postcode_id
LEFT JOIN LATERAL (
    SELECT wrs.current_status_id
    FROM welfare_request_status wrs
    WHERE wrs.applicant_id = ap.id
    ORDER BY wrs.updated_at DESC, wrs.id DESC
    LIMIT 1
) ls ON TRUE
LEFT JOIN current_status cs ON cs.id = ls.current_status_id
LEFT JOIN type_money_category tmc ON tmc.id = ap.type_money_category_id
"""


def _cases_filter_sql(filters: DashboardCaseFilters) -> tuple[str, dict]:
    clauses = [
        """(
            CAST(:province_ids AS int[]) IS NULL
            OR d.province_id = ANY(CAST(:province_ids AS int[]))
        )""",
        """(
            CAST(:type_money_ids AS int[]) IS NULL
            OR ap.type_money_category_id = ANY(CAST(:type_money_ids AS int[]))
        )""",
        """(
            CAST(:current_status_ids AS int[]) IS NULL
            OR ls.current_status_id = ANY(CAST(:current_status_ids AS int[]))
        )""",
    ]
    params: dict = {
        "province_ids": filters.province_ids,
        "type_money_ids": filters.type_money_ids,
        "current_status_ids": filters.current_status_ids,
    }
    if filters.case_number:
        clauses.append("ap.case_number ILIKE :case_number")
        params["case_number"] = f"%{filters.case_number}%"
    if filters.current_status:
        clauses.append("cs.description_staff ILIKE :current_status")
        params["current_status"] = f"%{filters.current_status}%"
    if filters.firstname:
        clauses.append("p.first_name ILIKE :firstname")
        params["firstname"] = f"%{filters.firstname}%"
    if filters.lastname:
        clauses.append("p.last_name ILIKE :lastname")
        params["lastname"] = f"%{filters.lastname}%"
    if filters.cid:
        clauses.append("p.cid ILIKE :cid")
        params["cid"] = f"%{filters.cid}%"
    if filters.datetime_create is not None:
        clauses.append("CAST(ap.created_at AS date) = CAST(:datetime_create AS date)")
        params["datetime_create"] = filters.datetime_create
    if filters.province_name:
        clauses.append("prov.name ILIKE :province_name")
        params["province_name"] = f"%{filters.province_name}%"
    if filters.district_id is not None:
        clauses.append("d.id = :district_id")
        params["district_id"] = filters.district_id
    if filters.district_name:
        clauses.append("d.name ILIKE :district_name")
        params["district_name"] = f"%{filters.district_name}%"
    if filters.subdistrict_id is not None:
        clauses.append("sd.id = :subdistrict_id")
        params["subdistrict_id"] = filters.subdistrict_id
    if filters.subdistrict_name:
        clauses.append("sd.name ILIKE :subdistrict_name")
        params["subdistrict_name"] = f"%{filters.subdistrict_name}%"
    if filters.subdistrict_postcode_id is not None:
        clauses.append("sdp.id = :subdistrict_postcode_id")
        params["subdistrict_postcode_id"] = filters.subdistrict_postcode_id
    if filters.postcode:
        clauses.append("pc.name ILIKE :postcode")
        params["postcode"] = f"%{filters.postcode}%"
    return " AND ".join(clauses), params


async def fetch_dashboard_cases_count(
    session: AsyncSession,
    filters: DashboardCaseFilters,
) -> int:
    where_sql, params = _cases_filter_sql(filters)
    sql = text(
        f"""
        SELECT COUNT(*)
        {_CASES_LOCATION_FROM}
        WHERE {where_sql}
        """
    )
    return await session.scalar(sql, params) or 0


async def fetch_dashboard_cases_page(
    session: AsyncSession,
    filters: DashboardCaseFilters,
    *,
    limit: int,
    offset: int,
) -> list[dict]:
    where_sql, params = _cases_filter_sql(filters)
    params = {**params, "limit": limit, "offset": offset}
    sql = text(
        f"""
        SELECT
            ap.id AS applicant_id,
            ap.case_number AS case_number,
            ls.current_status_id AS current_status_id,
            cs.description_staff AS current_status,
            cs.color AS current_status_color,
            ap.type_money_category_id AS type_money_id,
            tmc.name AS type_money_id_name,
            tmc.color AS type_money_id_color,
            tmc.name_acronym AS type_money_name_acronym,
            ap.sw_explorer_sdshv AS sw_explorer_sdshv,
            p.first_name AS firstname,
            p.last_name AS lastname,
            p.cid AS cid,
            COALESCE(
                GREATEST(0, EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.birth_date))::int),
                0
            ) AS person_age,
            ap.created_at AS datetime_create,
            ap.is_emergency AS is_emergency,
            ap.is_existing_case AS is_existing_case,
            ap.time_count_process AS time_count_process,
            ap.process_started_at AS process_started_at,
            ap.process_completed_at AS process_completed_at,
            ap.process_sla_days AS process_sla_days,
            prov.id AS province_id,
            prov.name AS province_name,
            d.id AS district_id,
            d.name AS district_name,
            sd.id AS subdistrict_id,
            sd.name AS subdistrict_name,
            sdp.id AS subdistrict_postcode_id,
            pc.name AS postcode,
            COALESCE(pay.count_037, 0) AS count_037,
            COALESCE(pay.count_038, 0) AS count_038,
            pay.is_037_or_038 AS is_037_or_038,
            EXISTS (
                SELECT 1
                FROM welfare_payment wp_dda
                JOIN welfare_dda_ref dda ON dda.id = wp_dda.dda_ref_id
                WHERE wp_dda.applicant_id = ap.id
            ) AS have_dda_ref,
            EXISTS (
                SELECT 1
                FROM approve_case ac
                WHERE ac.applicant_id = ap.id
                  AND ac.approve_status = true
            ) AS is_approved,
            EXISTS (
                SELECT 1
                FROM welfare_histories_detail whd
                WHERE whd.welfare_history_id = ap.id
                  AND whd.received_welfare_type_id IN {DISABILITY_RECEIVED_WELFARE_TYPE_IDS}
            ) AS is_disabled,
            ps.previous_status_id AS previous_status_id,
            EXISTS (
                SELECT 1
                FROM welfare_request_status s8
                JOIN welfare_request_status s1
                    ON s1.applicant_id = s8.applicant_id
                   AND s1.current_status_id = {CURRENT_STATUS_PENDING_INTAKE}
                   AND (
                       s1.updated_at > s8.updated_at
                       OR (s1.updated_at = s8.updated_at AND s1.id > s8.id)
                   )
                WHERE s8.applicant_id = ap.id
                  AND s8.current_status_id = {CURRENT_STATUS_EDIT_REQUESTED}
            ) AS is_return_edit_resubmitted,
            (
                pmj.pmj_reject_reason IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1
                    FROM approve_case ac_ok
                    WHERE ac_ok.applicant_id = ap.id
                      AND ac_ok.approve_status = true
                )
            ) AS is_pmj_rejected,
            CASE
                WHEN NOT EXISTS (
                    SELECT 1
                    FROM approve_case ac_ok
                    WHERE ac_ok.applicant_id = ap.id
                      AND ac_ok.approve_status = true
                )
                THEN pmj.pmj_reject_reason
                ELSE NULL
            END AS pmj_reject_reason,
            ch.responsible_division_id AS responsible_division_id,
            COALESCE(asa.require_ktb_corporate, true) AS require_ktb_corporate,
            COALESCE(asa.require_ktb_reason, 'NEW_CASE') AS require_ktb_reason,
            asa.existing_case_source AS existing_case_source,
            asa.existing_case_detected_sources AS existing_case_detected_sources,
            asa.existing_case_ref_id AS existing_case_ref_id,
            asa.existing_case_province_id AS existing_case_province_id,
            asa.existing_case_province_name AS existing_case_province_name,
            asa.submission_province_id AS submission_province_id,
            asa.submission_province_name AS submission_province_name,
            asa.is_account_changed AS is_account_changed,
            EXISTS (
                SELECT 1
                FROM welfare_evidences we
                WHERE we.applicant_id = ap.id
                  AND we.attachment_type_id = {ATTACHMENT_TYPE_KTB_CORPORATE}
            ) AS has_ktb_evidence
        {_CASES_LOCATION_FROM}
        LEFT JOIN LATERAL (
            SELECT wrs.current_status_id AS previous_status_id
            FROM welfare_request_status wrs
            WHERE wrs.applicant_id = ap.id
            ORDER BY wrs.updated_at DESC, wrs.id DESC
            OFFSET 1 LIMIT 1
        ) ps ON TRUE
        LEFT JOIN case_handling ch ON ch.applicant_id = ap.id
        LEFT JOIN applicant_submission_audit asa ON asa.applicant_id = ap.id
        LEFT JOIN LATERAL (
            SELECT ac.reject_reason AS pmj_reject_reason
            FROM approve_case ac
            WHERE ac.applicant_id = ap.id
              AND ac.approve_status = false
              AND ac.reject_reason IS NOT NULL
              AND ac.reject_resolved_at IS NULL
            ORDER BY ac.id DESC
            LIMIT 1
        ) pmj ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                COUNT(*) FILTER (WHERE wp.is_037_or_038 IS FALSE) AS count_037,
                COUNT(*) FILTER (WHERE wp.is_037_or_038 IS TRUE) AS count_038,
                (
                    SELECT wp2.is_037_or_038
                    FROM welfare_payment wp2
                    WHERE wp2.applicant_id = ap.id
                    ORDER BY wp2.id DESC
                    LIMIT 1
                ) AS is_037_or_038
            FROM welfare_payment wp
            WHERE wp.applicant_id = ap.id
        ) pay ON TRUE
        WHERE {where_sql}
        ORDER BY ap.created_at DESC, ap.id DESC
        LIMIT :limit OFFSET :offset
        """
    )
    rows = (await session.execute(sql, params)).mappings().all()
    return [dict(r) for r in rows]
