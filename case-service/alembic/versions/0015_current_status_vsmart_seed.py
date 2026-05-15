"""current_status: เพิ่ม vsmart_id และอัปเดต seed 9 สถานะ (สำหรับ DB ที่รัน 0009 เวอร์ชันเก่าแล้ว)

Revision ID: 0015_current_status_vsmart
Revises: 0014_attachment_types_family
Create Date: 2026-05-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_current_status_vsmart"
down_revision: str | Sequence[str] | None = "0014_attachment_types_family"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CURRENT_STATUS_ROWS: list[dict] = [
    {
        "id": 1,
        "description_public": "รอรับเรื่อง",
        "description_staff": "รอรับเรื่อง",
        "color": "#ffa500",
        "dropdown_to_change": "none",
        "dropdown_order": 0,
        "dropdown_activate": False,
        "filter_order": 0,
        "filter_activate": True,
        "vsmart_id": 2,
    },
    {
        "id": 2,
        "description_public": "รับเรื่องเรียบร้อย",
        "description_staff": "รับเรื่องเรียบร้อย",
        "color": "#009f75",
        "dropdown_to_change": "รับเรื่อง*",
        "dropdown_order": 1,
        "dropdown_activate": True,
        "filter_order": 1,
        "filter_activate": True,
        "vsmart_id": 3,
    },
    {
        "id": 3,
        "description_public": "อยู่ระหว่างการเบิก",
        "description_staff": "อยู่ระหว่างการเบิก",
        "color": "#ff0000",
        "dropdown_to_change": "อยู่ระหว่างการเบิก*",
        "dropdown_order": 2,
        "dropdown_activate": True,
        "filter_order": 2,
        "filter_activate": True,
        "vsmart_id": 15,
    },
    {
        "id": 4,
        "description_public": "เบิกจ่ายสำเร็จ",
        "description_staff": "ช่วยเหลือเเล้ว",
        "color": "#009f75",
        "dropdown_to_change": "ช่วยเหลือแล้ว*",
        "dropdown_order": 3,
        "dropdown_activate": True,
        "filter_order": 3,
        "filter_activate": True,
        "vsmart_id": 7,
    },
    {
        "id": 5,
        "description_public": "คุณสมบัติไม่ตรงตามหลักเกณฑ์",
        "description_staff": "คุณสมบัติไม่ตรงตามหลักเกณฑ์",
        "color": "#ff0000",
        "dropdown_to_change": "คุณสมบัติไม่ตรงตามหลักเกณฑ์",
        "dropdown_order": 8,
        "dropdown_activate": True,
        "filter_order": 8,
        "filter_activate": True,
        "vsmart_id": 12,
    },
    {
        "id": 6,
        "description_public": "อยู่ระหว่างการพิจารณาของคณะกรรมการ",
        "description_staff": "อยู่ระหว่างการพิจารณาของคณะกรรมการ",
        "color": "#0084ff",
        "dropdown_to_change": "อยู่ระหว่างการพิจารณาของคณะกรรมการ",
        "dropdown_order": 4,
        "dropdown_activate": False,
        "filter_order": 4,
        "filter_activate": False,
        "vsmart_id": 5,
    },
    {
        "id": 7,
        "description_public": "อยู่ระหว่างรอจัดสรรงบประมาณ",
        "description_staff": "อยู่ระหว่างรอจัดสรรงบประมาณ",
        "color": "#ffa500",
        "dropdown_to_change": "อยู่ระหว่างรอจัดสรรงบประมาณ",
        "dropdown_order": 5,
        "dropdown_activate": False,
        "filter_order": 5,
        "filter_activate": False,
        "vsmart_id": 13,
    },
    {
        "id": 8,
        "description_public": "เเก้ไขข้อมูล",
        "description_staff": "ดำเนินการแก้ไขข้อมูล",
        "color": "#ff0000",
        "dropdown_to_change": "แก้ไขข้อมูล",
        "dropdown_order": 6,
        "dropdown_activate": True,
        "filter_order": 6,
        "filter_activate": True,
        "vsmart_id": 8,
    },
    {
        "id": 9,
        "description_public": "อยู่ระหว่างการหาข้อมูลเพิ่มเติม",
        "description_staff": "อยู่ระหว่างการหาข้อมูลเพิ่มเติม",
        "color": "#48ff00",
        "dropdown_to_change": "อยู่ระหว่างการหาข้อมูลเพิ่มเติม",
        "dropdown_order": 7,
        "dropdown_activate": True,
        "filter_order": 7,
        "filter_activate": True,
        "vsmart_id": 9,
    },
]


def _upsert_by_id(table: str, rows: list[dict]) -> None:
    if not rows:
        return

    cols = [k for k in rows[0].keys()]
    if "id" not in cols:
        raise ValueError("seed rows must include id")

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

    bind = op.get_bind()
    bind.execute(sa.text(sql), rows)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    column_names = {col["name"] for col in inspector.get_columns("current_status")}

    if "vsmart_id" not in column_names:
        op.add_column("current_status", sa.Column("vsmart_id", sa.Integer(), nullable=True))

    _upsert_by_id("current_status", CURRENT_STATUS_ROWS)

    op.alter_column("current_status", "vsmart_id", existing_type=sa.Integer(), nullable=False)

    op.execute(
        sa.text(
            "SELECT setval(pg_get_serial_sequence('current_status', 'id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM current_status))"
        )
    )


def downgrade() -> None:
    raise NotImplementedError(
        "downgrade 0015_current_status_vsmart: ย้อน seed current_status ไม่ปลอดภัยอัตโนมัติ"
    )
