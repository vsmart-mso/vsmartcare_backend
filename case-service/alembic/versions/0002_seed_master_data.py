"""seed master data (excluding geo tables)

Revision ID: 0002_seed_master_data
Revises: 0001_initial_schema
Create Date: 2026-05-08 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_seed_master_data"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _upsert_by_id(table: str, rows: list[dict]) -> None:
    """
    Postgres upsert by `id` to make seed idempotent.

    Assumes every row has `id` key.
    """
    if not rows:
        return
    cols = [k for k in rows[0].keys()]
    if "id" not in cols:
        raise ValueError("seed rows must include id")

    # Build: INSERT INTO ... (cols...) VALUES (...) ON CONFLICT (id) DO UPDATE SET ...
    col_list = ", ".join(cols)
    value_placeholders = ", ".join([f":{c}" for c in cols])

    set_cols = [c for c in cols if c != "id"]
    if set_cols:
        set_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in set_cols])
        sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({value_placeholders}) "
            f"ON CONFLICT (id) DO UPDATE SET {set_clause}"
        )
    else:
        sql = f"INSERT INTO {table} ({col_list}) VALUES ({value_placeholders}) ON CONFLICT (id) DO NOTHING"

    # Alembic `op.execute()` ไม่รองรับส่ง parameter sets แบบ executemany ในบางเวอร์ชัน
    # ใช้ bind โดยตรงเพื่อให้ executemany ทำงานได้
    bind = op.get_bind()
    bind.execute(sa.text(sql), rows)


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────────
    # prefix_type
    # ──────────────────────────────────────────────────────────────
    _upsert_by_id(
        "prefix_type",
        [
            {"id": 1, "name": "นาย"},
            {"id": 2, "name": "นาง"},
            {"id": 3, "name": "นางสาว"},
        ],
    )

    # marital_status_types
    _upsert_by_id(
        "marital_status_types",
        [
            {"id": 1, "name": "โสด"},
            {"id": 2, "name": "สมรสอยู่ด้วยกัน"},
            {"id": 3, "name": "หย่าร้าง"},
            {"id": 4, "name": "ไม่ได้สมรสเเต่อยู่ด้วยกัน"},
            {"id": 5, "name": "หม้าย (คู่สมรสเสียชีวิต)"},
            {"id": 6, "name": "สมรสเเยกกันอยู่"},
        ],
    )

    # request_types ประเภทขอรับความช่วยเหลือ
    _upsert_by_id(
        "request_types",
        [
            {"id": 1, "name": "ช่วยเหลือเป็นเงิน"},
            {"id": 2, "name": "ช่วยเหลือเป็นสิ่งของ"},
            {"id": 3, "name": "ช่วยเหลือเรื่องอื่นๆ"},
        ],
    )

    # attachment_types (ตัวอย่างพื้นฐาน — ปรับเพิ่มได้ตามงานจริง)
    _upsert_by_id(
        "attachment_types",
        [
            {"id": 1, "name": "รูปหน้าสมุดบัญชีธนาคาร"},
            {"id": 2, "name": "รูปสภาพบ้านภายนอก"},
            {"id": 3, "name": "รูปสภาพบ้านภายใน"},
            {"id": 4, "name": "รูปผู้ประสบปัญหา"},
            {"id": 5, "name": "รูปสภาพปัญหาที่ต้องการให้ความช่วยเหลือ"},
            {"id": 6, "name": "รูปทะเบียนบ้าน (รายการเกี่ยวกับบ้าน)"},
            {"id": 7, "name": "รูปทะเบียนบ้าน (รายการเกี่ยวกับบุคคล)"},
            {"id": 8, "name": "รูปอื่น ๆ"},
        ],
    )

    # received_welfare_types ประเภทสวัสดิการที่เคยได้รับ
    _upsert_by_id(
        "received_welfare_types",
        [
            {"id": 1, "name": "เงินสงเคราะห์"},
            {"id": 2, "name": "เงินทุนประกอบอาชีพ"},
            {"id": 3, "name": "เงิน/เบี้ยผู้สูงอายุ (เบี้ยยังชีพผู้สูงอายุ)"},
            {"id": 4, "name": "เงิน/เบี้ยคนพิการ (เบี้ยความพิการ)"},
            {"id": 5, "name": "เงิน/เบี้ยเด็กแรกเกิด (เงินอุดหนุนเพื่อการเลี้ยงดูเด็กแรกเกิด)"},
            {"id": 6, "name": "บัตรคนจน (สวัสดิการที่ได้จากการลงทะเบียนโครงการเพื่อสวัสดิการแห่งรัฐ)"},
            {"id": 7, "name": "การซ่อมบ้าน (เงินซ่อมแซมบ้าน)"},
            {"id": 8, "name": "ความช่วยเหลืออื่นจากภาครัฐ"},
            {"id": 9, "name": "ความช่วยเหลืออื่นจากภาคเอกชน"},
            {"id": 10, "name": "เงินกู้"},
            {"id": 11, "name": "เครื่องช่วยความพิการ"},
            {"id": 99, "name": "อื่น ๆ"},
        ],
    )

    # dependency_types
    _upsert_by_id(
        "dependency_types",
        [
            {"id": 1, "name": "อุปการะเลี้ยงดูบิดามารดา"},
            {"id": 2, "name": "อุปการะเลี้ยงดูบุตร"},
            {"id": 3, "name": "อุปการะเลี้ยงดูผู้สูงอายุ"},
            {"id": 4, "name": "อุปการะเลี้ยงดูคนพิการหรือคนทุพพลภาพ"},
            {"id": 99, "name": "อื่น ๆ"},
        ],
    )

    # housing_types
    _upsert_by_id(
        "housing_types",
        [
            {"id": 1, "name": "มีที่อยู่อาศัยเป็นของตนเองและมั่นคงถาวร"},
            {"id": 2, "name": "มีที่อยู่อาศัยเป็นของตนเองแต่ไม่มั่นคงถาวร "},
            {"id": 3, "name": "อยู่ที่ดินบุคคลอื่น"},
            {"id": 99, "name": "บ้านเช่า"},
        ],
    )

    # income_source_types
    _upsert_by_id(
        "income_source_types",
        [
            {"id": 1, "name": "การประกอบอาชีพ"},
            {"id": 2, "name": "บุตร/ผู้อุปการะ"},
            {"id": 3, "name": "สวัสดิการของรัฐ"},
            {"id": 99, "name": "อื่น ๆ"},
        ],
    )

    # address_type
    _upsert_by_id(
        "address_type",
        [
            {"id": 1, "name": "ที่อยู่ปัจจุบัน"},
        ],
    )

    # current_status
    _upsert_by_id(
        "current_status",
        [
            {"id": 1, "name": "รับเรื่อง", "description": "นักสังคมรับพิจารณาเเล้ว"},
            {"id": 2, "name": "อยู่ระหว่างการเบิก", "description": "อยู่ในขั้นตอนการเบิกจ่ายเงิน"},
            {"id": 3, "name": "เบิกจ่ายสำเร็จ", "description": "ทำการเบิกจ่ายเงินสำเร็จเเล้ว"},
            {"id": 4, "name": "ไม่ตรงตามหลักเกณฑ์", "description": "คุณสมบัติไม่ตรงตามหลักเกณฑ์"},
        ],
    )


def downgrade() -> None:
    # ลบเฉพาะ id ที่ seed ไว้ (กันกระทบข้อมูลอื่นที่เพิ่มภายหลัง)
    op.execute(sa.text("DELETE FROM current_status WHERE id IN (1,2,3,4,5)"))
    op.execute(sa.text("DELETE FROM address_type WHERE id IN (1)"))
    op.execute(sa.text("DELETE FROM income_source_types WHERE id IN (1,2,3,99)"))
    op.execute(sa.text("DELETE FROM housing_types WHERE id IN (1,2,3,99)"))
    op.execute(sa.text("DELETE FROM dependency_types WHERE id IN (1,2,3,4,99)"))
    op.execute(sa.text("DELETE FROM received_welfare_types WHERE id IN (1,2,3,4,5,6,7,8,9,10,11,99)"))
    op.execute(sa.text("DELETE FROM attachment_types WHERE id IN (1,2,3,4)"))
    op.execute(sa.text("DELETE FROM request_types WHERE id IN (1,2,3)"))
    op.execute(sa.text("DELETE FROM marital_status_types WHERE id IN (1,2,3,4,5,6)"))
    op.execute(sa.text("DELETE FROM prefix_type WHERE id IN (1,2,3)"))
