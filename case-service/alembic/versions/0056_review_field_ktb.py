"""review_field: เพิ่ม doc_ktb_corporate สำหรับ KTB Corporate Online (ID 43, step 4)

Revision ID: 0056_review_field_ktb
Revises: 0055_attachment_types_ktb
Create Date: 2026-06-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0056_review_field_ktb"
down_revision: str | Sequence[str] | None = "0055_attachment_types_ktb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _upsert_by_id(table: str, rows: list[dict]) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    col_list = ", ".join(cols)
    value_placeholders = ", ".join([f":{c}" for c in cols])
    set_cols = [c for c in cols if c != "id"]
    set_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in set_cols])
    sql = (
        f"INSERT INTO {table} ({col_list}) VALUES ({value_placeholders}) "
        f"ON CONFLICT (id) DO UPDATE SET {set_clause}"
    )
    op.get_bind().execute(sa.text(sql), rows)


def upgrade() -> None:
    _upsert_by_id(
        "review_field",
        [
            {
                "id": 43,
                "name": "doc_ktb_corporate",
                "label": "รูปแบบฟอร์ม KTB Corporate Online",
                "step": 4,
                "display_order": 9,
                "is_active": True,
            }
        ],
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM review_field WHERE id = 43"))
