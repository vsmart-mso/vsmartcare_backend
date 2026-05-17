"""type_money master + FK case_handling.type_money_id (1:n)

Revision ID: 0026_type_money_case_handling
Revises: 0025_bank_name_mso_code_order
Create Date: 2026-05-17 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_type_money_case_handling"
down_revision: str | Sequence[str] | None = "0025_bank_name_mso_code_order"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TYPE_MONEY_ROWS: list[dict] = [
    {"id": 1, "name": "เงินอุดหนุน"},
    {"id": 2, "name": "เงินอุดหนุนเฉพาะกิจ"},
]


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
    op.create_table(
        "type_money",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_type_money")),
    )

    _upsert_by_id("type_money", TYPE_MONEY_ROWS)
    op.execute(
        sa.text(
            "SELECT setval(pg_get_serial_sequence('type_money', 'id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM type_money))"
        )
    )

    op.add_column(
        "case_handling",
        sa.Column("type_money_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_case_handling_type_money_id_type_money"),
        "case_handling",
        "type_money",
        ["type_money_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_case_handling_type_money_id"),
        "case_handling",
        ["type_money_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_case_handling_type_money_id"), table_name="case_handling")
    op.drop_constraint(
        op.f("fk_case_handling_type_money_id_type_money"),
        "case_handling",
        type_="foreignkey",
    )
    op.drop_column("case_handling", "type_money_id")
    op.drop_table("type_money")
