"""add ocr_results table

Revision ID: 0034_ocr_results
Revises: 0033_welfare_payment_reject
Create Date: 2026-05-19 10:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034_ocr_results"
down_revision: str | Sequence[str] | None = "0033_welfare_payment_reject"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ocr_results",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=True),
        sa.Column("target_name_checked", sa.Text(), nullable=False),
        sa.Column("pre_file", sa.String(length=255), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("account_number", sa.String(length=50), nullable=True),
        sa.Column("account_name", sa.Text(), nullable=True),
        sa.Column("bank_name", sa.Text(), nullable=True),
        sa.Column("match_status", sa.String(length=20), nullable=False, server_default=sa.text("'no_text'")),
        sa.Column("fuzzy_score", sa.Float(), nullable=False, server_default=sa.text("'0.0'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ocr_results")),
        sa.ForeignKeyConstraint(
            ["applicant_id"], ["applicants.id"],
            name=op.f("fk_ocr_results_applicant_id_applicants"),
            ondelete="SET NULL",
        ),
    )
    op.create_index(op.f("ix_ocr_results_applicant_id"), "ocr_results", ["applicant_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ocr_results_applicant_id"), table_name="ocr_results")
    op.drop_table("ocr_results")
