"""เพิ่ม bank_account_type_id (FK) + bank_branch_name ใน applicants (เก็บประเภทเงินฝาก/สาขาจาก OCR).

Revision ID: 0042_applicant_bank_extra
Revises: 0041_ocr_bank_extra_fields
Create Date: 2026-05-24 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042_applicant_bank_extra"
down_revision: str | Sequence[str] | None = "0041_ocr_bank_extra_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("applicants")}

    # ประเภทเงินฝาก — FK ไปยัง master bank_account_type (เงินฝากออมทรัพย์/ประจำ/กระแสรายวัน)
    if "bank_account_type_id" not in existing:
        op.add_column(
            "applicants",
            sa.Column("bank_account_type_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            op.f("fk_applicants_bank_account_type_id_bank_account_type"),
            "applicants",
            "bank_account_type",
            ["bank_account_type_id"],
            ["id"],
        )
        op.create_index(
            op.f("ix_applicants_bank_account_type_id"),
            "applicants",
            ["bank_account_type_id"],
        )

    # ชื่อสาขา — ข้อความที่ OCR อ่านได้ (เก็บตรงๆ ไม่ผูก lookup)
    if "bank_branch_name" not in existing:
        op.add_column(
            "applicants",
            sa.Column("bank_branch_name", sa.String(length=255), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("applicants", "bank_branch_name")
    op.drop_index(op.f("ix_applicants_bank_account_type_id"), table_name="applicants")
    op.drop_constraint(
        op.f("fk_applicants_bank_account_type_id_bank_account_type"),
        "applicants",
        type_="foreignkey",
    )
    op.drop_column("applicants", "bank_account_type_id")
