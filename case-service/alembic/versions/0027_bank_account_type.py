"""bank_account_type lookup + FK บน case_payment

Revision ID: 0027_bank_account_type
Revises: 0026_type_money_case_handling
Create Date: 2026-05-17 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_bank_account_type"
down_revision: str | Sequence[str] | None = "0026_type_money_case_handling"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEED_ROWS = [
    {"id": 1, "name": "เงินฝากออมทรัพย์", "sort_order": 1},
    {"id": 2, "name": "เงินฝากประจำ", "sort_order": 2},
    {"id": 3, "name": "เงินฝากกระแสรายวัน", "sort_order": 3},
]


def upgrade() -> None:
    op.create_table(
        "bank_account_type",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bank_account_type")),
    )

    op.get_bind().execute(
        sa.text(
            "INSERT INTO bank_account_type (id, name, sort_order) VALUES "
            "(:id, :name, :sort_order) ON CONFLICT (id) DO UPDATE SET "
            "name = EXCLUDED.name, sort_order = EXCLUDED.sort_order"
        ),
        SEED_ROWS,
    )
    op.execute(
        sa.text(
            "SELECT setval(pg_get_serial_sequence('bank_account_type', 'id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM bank_account_type))"
        )
    )

    op.add_column(
        "case_payment",
        sa.Column("bank_account_type_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_case_payment_bank_account_type_id_bank_account_type"),
        "case_payment",
        "bank_account_type",
        ["bank_account_type_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_case_payment_bank_account_type_id"),
        "case_payment",
        ["bank_account_type_id"],
        unique=False,
    )
    op.drop_column("case_payment", "account_type")


def downgrade() -> None:
    op.add_column(
        "case_payment",
        sa.Column("account_type", sa.String(length=100), nullable=True),
    )
    op.drop_index(
        op.f("ix_case_payment_bank_account_type_id"), table_name="case_payment"
    )
    op.drop_constraint(
        op.f("fk_case_payment_bank_account_type_id_bank_account_type"),
        "case_payment",
        type_="foreignkey",
    )
    op.drop_column("case_payment", "bank_account_type_id")
    op.drop_table("bank_account_type")
