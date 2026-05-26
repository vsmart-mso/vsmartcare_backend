"""current_status: เพิ่มสถานะ id=11 ส่งต่อข้อมูลเรียบร้อยแล้ว

Revision ID: 0048_current_status_id_11
Revises: 0047_applicant_process_completed_at
Create Date: 2026-05-26 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0048_current_status_id_11"
down_revision: str | Sequence[str] | None = "0047_applicant_process_completed_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CURRENT_STATUS_ROW: dict = {
    "id": 11,
    "description_staff": "ส่งต่อข้อมูลเรียบร้อยแล้ว",
    "description_public": "ส่งต่อข้อมูลเรียบร้อยแล้ว",
    "color": "#009f75",
    "dropdown_to_change": "ส่งต่อข้อมูลเรียบร้อยแล้ว",
    "dropdown_order": 9,
    "dropdown_activate": False,
    "filter_order": 9,
    "filter_activate": True,
    # แมป VSmart — ปรับได้ถ้าระบบต้นทางใช้รหัสอื่น
    "vsmart_id": 14,
}


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
    _upsert_by_id("current_status", [CURRENT_STATUS_ROW])
    op.execute(
        sa.text(
            "SELECT setval(pg_get_serial_sequence('current_status', 'id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM current_status))"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM current_status WHERE id = 11"))
