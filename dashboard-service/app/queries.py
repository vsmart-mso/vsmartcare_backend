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


async def fetch_dashboard_situation_export_rows(
    session: AsyncSession,
    *,
    province_ids: list[int] | None,
    applicant_ids: list[int] | None,
    district_ids: list[int] | None,
    sub_district_ids: list[int] | None,
    current_status_ids: list[int] | None,
    type_money_ids: list[int] | None,
) -> list[dict]:
    """ข้อมูลรายงานสถานการณ์ตามขั้นตอนธุรกิจและหน่วยงานที่รับผิดชอบ."""
    sql = text(
        """
        WITH primary_address AS (
            SELECT
                a.applicant_id,
                a.sub_district_postcode_id,
                ROW_NUMBER() OVER (
                    PARTITION BY a.applicant_id
                    ORDER BY a.id ASC
                ) AS rn
            FROM address a
        ),
        latest_status AS (
            SELECT
                wrs.applicant_id,
                wrs.current_status_id,
                cs.description_staff AS status_name,
                cs.color AS status_color,
                ROW_NUMBER() OVER (
                    PARTITION BY wrs.applicant_id
                    ORDER BY wrs.updated_at DESC, wrs.id DESC
                ) AS rn
            FROM welfare_request_status wrs
            JOIN current_status cs ON cs.id = wrs.current_status_id
        ),
        situation_cases AS (
            SELECT
                ap.id AS applicant_id,
                ap.case_number,
                p.first_name,
                p.last_name,
                ap.type_money_category_id,
                tmc.name AS type_money_category_name,
                tmc.name_acronym AS type_money_category_acronym,
                ls.current_status_id,
                ls.status_name AS current_status_label,
                ls.status_color,
                EXISTS (
                    SELECT 1
                    FROM approve_case ac
                    WHERE ac.applicant_id = ap.id
                      AND ac.approve_status = true
                ) AS is_approved,
                ap.created_at,
                d.province_id,
                d.id AS district_id,
                sd.id AS sub_district_id
            FROM applicants ap
            JOIN primary_address pa
              ON pa.applicant_id = ap.id
             AND pa.rn = 1
            JOIN sub_districts_postcode sdp
              ON sdp.id = pa.sub_district_postcode_id
            JOIN sub_districts sd ON sd.id = sdp.sub_district_id
            JOIN districts d ON d.id = sd.district_id
            JOIN province prov ON prov.id = d.province_id
            LEFT JOIN persons p ON p.id = ap.persons_id
            LEFT JOIN type_money_category tmc ON tmc.id = ap.type_money_category_id
            LEFT JOIN latest_status ls
              ON ls.applicant_id = ap.id
             AND ls.rn = 1
            WHERE (
                CAST(:province_ids AS int[]) IS NULL
                OR d.province_id = ANY(CAST(:province_ids AS int[]))
            )
              AND (
                CAST(:applicant_ids AS int[]) IS NULL
                OR ap.id = ANY(CAST(:applicant_ids AS int[]))
              )
              AND (
                CAST(:district_ids AS int[]) IS NULL
                OR d.id = ANY(CAST(:district_ids AS int[]))
              )
              AND (
                CAST(:sub_district_ids AS int[]) IS NULL
                OR sd.id = ANY(CAST(:sub_district_ids AS int[]))
              )
              AND (
                CAST(:type_money_ids AS int[]) IS NULL
                OR ap.type_money_category_id = ANY(CAST(:type_money_ids AS int[]))
              )
              AND (
                CAST(:current_status_ids AS int[]) IS NULL
                OR ls.current_status_id = ANY(CAST(:current_status_ids AS int[]))
              )
        )
        SELECT
            case_number,
            first_name,
            last_name,
            COALESCE(type_money_category_acronym, '-') AS type_money_category_acronym,
            type_money_category_name,
            current_status_id,
            current_status_label,
            CASE
                WHEN current_status_id = 1 AND type_money_category_id IS NULL
                    THEN 'รอรับเรื่อง (ยังไม่เลือกกลุ่มเป้าหมาย)'
                WHEN current_status_id = 1 AND type_money_category_id IS NOT NULL
                    THEN 'รอรับเรื่อง (เลือกกลุ่มเป้าหมายแล้ว)'
                WHEN current_status_id = 2 THEN 'รับเรื่องเรียบร้อย'
                WHEN current_status_id = 8 THEN 'แก้ไขข้อมูล'
                WHEN current_status_id = 9 THEN 'อยู่ระหว่างหาข้อมูลเพิ่มเติม'
                WHEN current_status_id = 3 AND NOT is_approved
                    THEN 'อยู่ระหว่างการเบิก (รออนุมัติ)'
                WHEN current_status_id = 3 AND is_approved
                    THEN 'อยู่ระหว่างการเบิก (อนุมัติแล้ว)'
                WHEN current_status_id = 10
                    THEN 'อยู่ระหว่างการเบิก สีฟ้า / เบิกจ่ายสำเร็จ'
                WHEN current_status_id = 4
                    THEN 'ช่วยเหลือแล้ว / เบิกจ่ายสำเร็จ'
                WHEN current_status_id = 5 THEN 'คุณสมบัติไม่ตรงตามหลักเกณฑ์'
                WHEN current_status_id = 11 THEN 'ส่งต่อข้อมูลเรียบร้อยแล้ว'
                ELSE COALESCE(current_status_label, '(ไม่มีสถานะ)')
            END AS current_status_business_step,
            CASE
                WHEN current_status_id = 1 AND type_money_category_id IS NULL
                    THEN 'เจ้าหน้าที่ 1300 (นักพัฒนาสังคม)'
                WHEN current_status_id = 1 AND type_money_category_id IS NOT NULL
                    THEN 'นักสังคมสงเคราะห์ (วินิจฉัย)'
                WHEN current_status_id IN (2, 9)
                    THEN 'นักสังคมสงเคราะห์ (วินิจฉัย)'
                WHEN current_status_id = 8 THEN 'ประชาชน (แก้ไขข้อมูล)'
                WHEN current_status_id = 3 AND NOT is_approved THEN 'ผู้อนุมัติ'
                WHEN current_status_id = 3 AND is_approved THEN 'การเงิน'
                WHEN current_status_id IN (4, 10) THEN 'เบิกจ่ายสำเร็จ'
                WHEN current_status_id = 5 THEN 'จบ (ไม่ผ่าน)'
                WHEN current_status_id = 11 THEN 'จบ (ส่งต่อ MSO/กระทรวง)'
                ELSE NULL
            END AS responsible_person,
            created_at
        FROM situation_cases
        ORDER BY current_status_id NULLS LAST, case_number
        """
    )
    rows = (
        await session.execute(
            sql,
            {
                "province_ids": province_ids,
                "applicant_ids": applicant_ids,
                "district_ids": district_ids,
                "sub_district_ids": sub_district_ids,
                "current_status_ids": current_status_ids,
                "type_money_ids": type_money_ids,
            },
        )
    ).mappings().all()
    return [dict(row) for row in rows]


async def fetch_dashboard_case_list(
    session: AsyncSession,
    *,
    province_ids: list[int] | None,
    district_id: int | None,
    current_status_ids: list[int] | None,
    type_money_ids: list[int] | None,
    search: str | None,
    date_from,
    date_to,
    limit: int,
    offset: int,
) -> dict:
    """รายการเคสรายบุคคลในพื้นที่สำหรับ Modal บนแผนที่."""
    sql = text(
        """
        WITH case_rows AS (
            SELECT
                ap.id AS applicant_id,
                ap.case_number,
                p.first_name,
                p.last_name,
                ap.created_at,
                tmc.name_acronym AS type_money_name_acronym,
                tmc.name AS type_money_name,
                ls.current_status_id,
                cs.description_staff AS current_status,
                cs.color AS current_status_color,
                prov.name AS province_name,
                d.id AS district_id,
                d.name AS district_name,
                sd.name AS sub_district_name
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
            LEFT JOIN type_money_category tmc ON tmc.id = ap.type_money_category_id
            LEFT JOIN LATERAL (
                SELECT wrs.current_status_id
                FROM welfare_request_status wrs
                WHERE wrs.applicant_id = ap.id
                ORDER BY wrs.updated_at DESC, wrs.id DESC
                LIMIT 1
            ) ls ON TRUE
            JOIN current_status cs
              ON cs.id = ls.current_status_id
             AND cs.filter_activate = true
            WHERE (
                CAST(:province_ids AS int[]) IS NULL
                OR d.province_id = ANY(CAST(:province_ids AS int[]))
              )
              AND (
                CAST(:district_id AS int) IS NULL
                OR d.id = CAST(:district_id AS int)
              )
              AND (
                CAST(:current_status_ids AS int[]) IS NULL
                OR ls.current_status_id = ANY(CAST(:current_status_ids AS int[]))
              )
              AND (
                CAST(:type_money_ids AS int[]) IS NULL
                OR ap.type_money_category_id = ANY(CAST(:type_money_ids AS int[]))
              )
              AND (
                CAST(:search AS text) IS NULL
                OR ap.case_number ILIKE '%' || CAST(:search AS text) || '%'
                OR p.first_name ILIKE '%' || CAST(:search AS text) || '%'
                OR p.last_name ILIKE '%' || CAST(:search AS text) || '%'
                OR concat_ws(' ', p.first_name, p.last_name) ILIKE '%' || CAST(:search AS text) || '%'
              )
              AND (
                CAST(:date_from AS date) IS NULL
                OR (ap.created_at AT TIME ZONE 'Asia/Bangkok')::date >= CAST(:date_from AS date)
              )
              AND (
                CAST(:date_to AS date) IS NULL
                OR (ap.created_at AT TIME ZONE 'Asia/Bangkok')::date <= CAST(:date_to AS date)
              )
        )
        SELECT *, COUNT(*) OVER() AS total_items
        FROM case_rows
        ORDER BY created_at DESC, applicant_id DESC
        LIMIT :limit OFFSET :offset
        """
    )
    rows = (
        await session.execute(
            sql,
            {
                "province_ids": province_ids,
                "district_id": district_id,
                "current_status_ids": current_status_ids,
                "type_money_ids": type_money_ids,
                "search": search or None,
                "date_from": date_from,
                "date_to": date_to,
                "limit": limit,
                "offset": offset,
            },
        )
    ).mappings().all()
    items = [dict(row) for row in rows]
    total_items = int(items[0].pop("total_items")) if items else 0
    for item in items[1:]:
        item.pop("total_items", None)
    return {"total_items": total_items, "items": items}


async def fetch_dashboard_case_export_rows(
    session: AsyncSession,
    *,
    province_ids: list[int] | None,
    district_ids: list[int] | None,
    sub_district_ids: list[int] | None,
    current_status_ids: list[int] | None,
    type_money_ids: list[int] | None,
    exclude_province_ids: list[int] | None = None,
) -> list[dict]:
    """รายละเอียดรายคำร้องสำหรับ Excel dashboard.

    ใช้ CTE ตำแหน่งภูมิศาสตร์ชุดเดียวกับ dashboard summary เพื่อให้ผลลัพธ์ตรงกับ filter
    บนหน้าจอ แล้วค่อย LEFT JOIN ข้อมูลประกอบที่อาจยังไม่มีในแต่ละเคส.
    """
    sql = text(
        """
        WITH export_cases AS (
            SELECT
                ap.id AS applicant_id,
                ap.case_number,
                ap.created_at,
                ap.is_emergency,
                ap.is_existing_case,
                ap.age AS applicant_age,
                ap.mobile_phone,
                ap.home_phone,
                ap.fax_number,
                ap.email_address,
                ap.is_government_officer,
                ap.problem_details,
                ap.family_distress,
                ap.sw_explorer_sdshv,
                ap.type_money_category_id,
                p.cid,
                p.first_name,
                p.last_name,
                p.birth_date,
                p.gender,
                d.province_id,
                prov.name AS province_name,
                d.id AS district_id,
                d.name AS district_name,
                sd.id AS sub_district_id,
                sd.name AS sub_district_name,
                pc.name AS postcode,
                pa.house_number,
                pa.house_moo,
                pa.house_name,
                pa.road,
                pa.alley,
                pa.sub_lane,
                pa.mobile_phone AS address_mobile_phone,
                pa.latitude,
                pa.longitude,
                pa.nearby_landmark,
                ls.current_status_id,
                ls.update_by_sdshv AS latest_status_update_by
            FROM applicants ap
            JOIN persons p ON p.id = ap.persons_id
            LEFT JOIN LATERAL (
                SELECT a.*
                FROM address a
                WHERE a.applicant_id = ap.id
                ORDER BY a.address_type_id DESC, a.id ASC
                LIMIT 1
            ) pa ON TRUE
            JOIN sub_districts_postcode sdp
                ON sdp.id = COALESCE(pa.sub_district_postcode_id, p.sub_district_postcode_id)
            JOIN sub_districts sd ON sd.id = sdp.sub_district_id
            JOIN districts d ON d.id = sd.district_id
            JOIN province prov ON prov.id = d.province_id
            LEFT JOIN postcode pc ON pc.id = sdp.postcode_id
            LEFT JOIN LATERAL (
                SELECT wrs.current_status_id, wrs.update_by_sdshv
                FROM welfare_request_status wrs
                WHERE wrs.applicant_id = ap.id
                ORDER BY wrs.updated_at DESC, wrs.id DESC
                LIMIT 1
            ) ls ON TRUE
            JOIN current_status active_cs
                ON active_cs.id = ls.current_status_id
               AND active_cs.filter_activate = true
            WHERE (
                CAST(:province_ids AS int[]) IS NULL
                OR d.province_id = ANY(CAST(:province_ids AS int[]))
            )
              AND (
                CAST(:exclude_province_ids AS int[]) IS NULL
                OR NOT (d.province_id = ANY(CAST(:exclude_province_ids AS int[])))
              )
              AND (
                CAST(:district_ids AS int[]) IS NULL
                OR d.id = ANY(CAST(:district_ids AS int[]))
              )
              AND (
                CAST(:sub_district_ids AS int[]) IS NULL
                OR sd.id = ANY(CAST(:sub_district_ids AS int[]))
              )
              AND (
                CAST(:type_money_ids AS int[]) IS NULL
                OR ap.type_money_category_id = ANY(CAST(:type_money_ids AS int[]))
              )
              AND (
                CAST(:current_status_ids AS int[]) IS NULL
                OR ls.current_status_id = ANY(CAST(:current_status_ids AS int[]))
              )
        )
        SELECT
            ec.*,
            cs.description_staff AS current_status_label,
            cs.description_public AS current_status_public_label,
            cs.dropdown_to_change AS current_status_business_step,
            tmc.name AS type_money_category_name,
            tmc.name_acronym AS type_money_category_acronym,
            mst.name AS marital_status_name,
            rrt.name AS requester_relation_name,
            ei.monthly_income,
            ei.household_members AS household_members_count,
            ei.housing_types_rent,
            ei.housing_shelter,
            COALESCE(occ.name, ei.occupation) AS occupation_name,
            COALESCE(focc.name, ei.family_occupation) AS family_occupation_name,
            ht.name AS housing_type_name,
            wh.has_received_welfare,
            wh.received_count,
            wh.total_received_amount,
            ch.sw_user_sdshv,
            tm.name AS type_money_name,
            crc.money_amount AS approved_money_amount,
            crc.comment AS regulation_comment,
            ar.name AS regulation_name,
            pm.name_th AS payment_method_name,
            COALESCE(payee.first_name || ' ' || payee.last_name, cp.account_name) AS payee_name,
            payee.cid AS payee_cid,
            cbn.name AS payment_bank_name,
            cp.account_number,
            cp.account_name,
            cp.bank_branch,
            cp.cheque_reference,
            income_sources.names AS income_source_names,
            dependency.names AS dependency_names,
            welfare_types.names AS received_welfare_type_names,
            request_types.names AS request_type_names,
            request_types.in_kind_text AS request_in_kind_text,
            request_types.other_text AS request_other_text,
            household.details AS household_member_details,
            diagnosis.diagnosis_text,
            diagnosis.owner_name AS social_worker_name,
            diagnosis.owner_position AS social_worker_position,
            diagnosis.owner_organization AS social_worker_organization,
            audit.existing_case_source,
            audit.existing_case_detected_sources,
            audit.existing_case_ref_id
        FROM export_cases ec
        LEFT JOIN current_status cs ON cs.id = ec.current_status_id
        LEFT JOIN applicants ap ON ap.id = ec.applicant_id
        LEFT JOIN type_money_category tmc ON tmc.id = ap.type_money_category_id
        LEFT JOIN marital_status_types mst ON mst.id = ap.marital_status_id
        LEFT JOIN requester_relation_type rrt ON rrt.id = ap.requester_relation_id
        LEFT JOIN LATERAL (
            SELECT e.*
            FROM economic_infos e
            WHERE e.applicant_id = ec.applicant_id
            ORDER BY e.id DESC
            LIMIT 1
        ) ei ON TRUE
        LEFT JOIN occupation_types occ ON occ.id = ei.occupation_type_id
        LEFT JOIN occupation_types focc ON focc.id = ei.family_occupation_type_id
        LEFT JOIN housing_types ht ON ht.id = ei.housing_types_id
        LEFT JOIN welfare_histories wh ON wh.applicant_id = ec.applicant_id
        LEFT JOIN case_handling ch ON ch.applicant_id = ec.applicant_id
        LEFT JOIN type_money tm ON tm.id = ch.type_money_id
        LEFT JOIN case_regulation_choice crc ON crc.case_handling_id = ch.id
        LEFT JOIN announcement_regulations ar ON ar.id = crc.regulation_id
        LEFT JOIN case_payment cp ON cp.case_handling_id = ch.id
        LEFT JOIN payment_method pm ON pm.id = cp.payment_method_id
        LEFT JOIN persons payee ON payee.id = cp.payee_person_id
        LEFT JOIN bank_name cbn ON cbn.id = cp.bank_name_id
        LEFT JOIN applicant_submission_audit audit ON audit.applicant_id = ec.applicant_id
        LEFT JOIN LATERAL (
            SELECT string_agg(
                COALESCE(ist.name, eis.other_details),
                ', ' ORDER BY ist.id
            ) AS names
            FROM economic_income_sources eis
            LEFT JOIN income_source_types ist ON ist.id = eis.income_source_type_id
            WHERE eis.economic_id = ei.id
        ) income_sources ON TRUE
        LEFT JOIN LATERAL (
            SELECT string_agg(
                COALESCE(dt.name, dl.dependency_other_text),
                ', ' ORDER BY dt.id
            ) AS names
            FROM dependency_loads dl
            LEFT JOIN dependency_types dt ON dt.id = dl.dependency_type_id
            WHERE dl.applicant_id = ec.applicant_id
        ) dependency ON TRUE
        LEFT JOIN LATERAL (
            SELECT string_agg(
                COALESCE(rwt.name, whd.received_other),
                ', ' ORDER BY rwt.id
            ) AS names
            FROM welfare_histories_detail whd
            LEFT JOIN received_welfare_types rwt ON rwt.id = whd.received_welfare_type_id
            WHERE whd.welfare_history_id = ec.applicant_id
        ) welfare_types ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                string_agg(rt.name, ', ' ORDER BY rt.id) AS names,
                string_agg(wrt.request_in_kind_text, ', ' ORDER BY rt.id) FILTER (
                    WHERE wrt.request_in_kind_text IS NOT NULL AND wrt.request_in_kind_text <> ''
                ) AS in_kind_text,
                string_agg(wrt.request_other_text, ', ' ORDER BY rt.id) FILTER (
                    WHERE wrt.request_other_text IS NOT NULL AND wrt.request_other_text <> ''
                ) AS other_text
            FROM welfare_request_types wrt
            LEFT JOIN request_types rt ON rt.id = wrt.request_type_id
            WHERE wrt.applicant_id = ec.applicant_id
        ) request_types ON TRUE
        LEFT JOIN LATERAL (
            SELECT string_agg(
                concat_ws(
                    ' ',
                    hm.seq::text || '.',
                    trim(concat_ws(' ', hm.first_name, hm.last_name)),
                    NULLIF('ความสัมพันธ์: ' || COALESCE(hmrt.name, ''), 'ความสัมพันธ์: '),
                    NULLIF('อาชีพ: ' || COALESCE(ot.name, hm.occupation, ''), 'อาชีพ: '),
                    NULLIF('รายได้: ' || COALESCE(hm.monthly_income::text, ''), 'รายได้: ')
                ),
                E'\n' ORDER BY hm.seq
            ) AS details
            FROM household_members hm
            LEFT JOIN household_member_relation_types hmrt ON hmrt.id = hm.relation_to_applicant_id
            LEFT JOIN occupation_types ot ON ot.id = hm.occupation_type_id
            WHERE hm.applicant_id = ec.applicant_id
        ) household ON TRUE
        LEFT JOIN LATERAL (
            SELECT
                string_agg(cd.diagnosis_text, E'\n' ORDER BY cd.updated_at DESC, cd.id DESC) AS diagnosis_text,
                (array_agg(cd.owner_name ORDER BY cd.updated_at DESC, cd.id DESC))[1] AS owner_name,
                (array_agg(cd.owner_position ORDER BY cd.updated_at DESC, cd.id DESC))[1] AS owner_position,
                (array_agg(cd.owner_organization ORDER BY cd.updated_at DESC, cd.id DESC))[1] AS owner_organization
            FROM case_diagnosis cd
            WHERE cd.applicant_id = ec.applicant_id
        ) diagnosis ON TRUE
        ORDER BY ec.created_at DESC, ec.applicant_id DESC
        """
    )
    rows = (
        await session.execute(
            sql,
            {
                "province_ids": province_ids,
                "exclude_province_ids": exclude_province_ids,
                "district_ids": district_ids,
                "sub_district_ids": sub_district_ids,
                "current_status_ids": current_status_ids,
                "type_money_ids": type_money_ids,
            },
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
