"""reassign attachment_types id 8 to family member; move other photos to id 99

Revision ID: 0014_attachment_types_family
Revises: 0013_money_category_payment
Create Date: 2026-05-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_attachment_types_family"
down_revision: str | Sequence[str] | None = "0013_money_category_payment"
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
            {"id": 99, "name": "รูปอื่น ๆ"},
        ],
    )

    op.execute(
        sa.text(
            """
            UPDATE welfare_evidences
            SET attachment_type_id = 99
            WHERE attachment_type_id = 8
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE file_payment
            SET attachment_type_id = 99
            WHERE attachment_type_id = 8
            """
        )
    )

    op.execute(sa.text("DELETE FROM attachment_types WHERE id = 8"))

    _upsert_by_id(
        "attachment_types",
        [
            {"id": 8, "name": "รูปสมาชิกในครอบครัว"},
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE welfare_evidences
            SET attachment_type_id = 8
            WHERE attachment_type_id = 99
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE file_payment
            SET attachment_type_id = 8
            WHERE attachment_type_id = 99
            """
        )
    )

    op.execute(sa.text("DELETE FROM attachment_types WHERE id = 8"))

    _upsert_by_id(
        "attachment_types",
        [
            {"id": 8, "name": "รูปอื่น ๆ"},
        ],
    )

    op.execute(sa.text("DELETE FROM attachment_types WHERE id = 99"))
