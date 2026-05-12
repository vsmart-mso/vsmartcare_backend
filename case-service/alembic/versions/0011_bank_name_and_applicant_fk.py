"""bank_name master table + applicants.bank_name_id FK

Revision ID: 0011_bank_name_applicant_fk
Revises: 0010_case_number_unique
Create Date: 2026-05-12 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_bank_name_applicant_fk"
down_revision: str | Sequence[str] | None = "0010_case_number_unique"
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
    op.create_table(
        "bank_name",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    _upsert_by_id(
        "bank_name",
        [
            {"id": 1, "name": "ธนาคารกรุงไทย"},
            {"id": 2, "name": "ธนาคารกรุงเทพ"},
            {"id": 3, "name": "ธนาคารกสิกรไทย"},
            {"id": 4, "name": "ธนาคารไทยพาณิชย์"},
            {"id": 5, "name": "ธนาคารออมสิน"},
            {"id": 6, "name": "ธนาคารเพื่อการเกษตรเเละสหกรณ์การเกษตร (ธ.ก.ส)"},
            {"id": 7, "name": "ธนาคารกรุงศรีอยุธยา"},
            {"id": 8, "name": "ธนาคารทหารไทยธนชาต (ttb)"},
        ],
    )

    op.add_column("applicants", sa.Column("bank_name_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_applicants_bank_name_id"), "applicants", ["bank_name_id"], unique=False)
    op.create_foreign_key(
        "fk_applicants_bank_name_id_bank_name",
        "applicants",
        "bank_name",
        ["bank_name_id"],
        ["id"],
    )
    op.drop_column("applicants", "bank_account_name")


def downgrade() -> None:
    op.add_column("applicants", sa.Column("bank_account_name", sa.String(length=255), nullable=True))
    op.drop_constraint("fk_applicants_bank_name_id_bank_name", "applicants", type_="foreignkey")
    op.drop_index(op.f("ix_applicants_bank_name_id"), table_name="applicants")
    op.drop_column("applicants", "bank_name_id")
    op.drop_table("bank_name")
