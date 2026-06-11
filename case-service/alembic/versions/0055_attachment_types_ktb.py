"""attachment_types: เพิ่มแบบฟอร์ม KTB Corporate Online (ID 11)

Revision ID: 0055_attachment_types_ktb
Revises: 0054_household_member_dob
Create Date: 2026-06-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0055_attachment_types_ktb"
down_revision: str | Sequence[str] | None = "0054_household_member_dob"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
    _upsert_by_id(
        "attachment_types",
        [
            {"id": 11, "name": "รูปแบบแจ้งข้อมูลการรับเงินโอนผ่านระบบ KTB Corporate Online"},
        ],
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM attachment_types WHERE id = 11"))
