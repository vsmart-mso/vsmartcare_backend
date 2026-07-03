"""applicant_submission_audit — snapshot Require KTB ตอนยื่นคำร้อง (1:1 applicants)

Revision ID: 0071_applicant_submission_audit
Revises: 0070_case_diagnosis
Create Date: 2026-07-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0071_applicant_submission_audit"
down_revision: str | None = "0070_case_diagnosis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applicant_submission_audit",
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("existing_case_source", sa.String(length=16), nullable=True),
        sa.Column("existing_case_ref_id", sa.Integer(), nullable=True),
        sa.Column("existing_case_province_id", sa.Integer(), nullable=True),
        sa.Column("existing_case_province_name", sa.String(length=255), nullable=True),
        sa.Column("submission_province_id", sa.Integer(), nullable=True),
        sa.Column("submission_province_name", sa.String(length=255), nullable=True),
        sa.Column("is_account_changed", sa.Boolean(), nullable=True),
        sa.Column(
            "require_ktb_corporate",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "require_ktb_reason",
            sa.String(length=32),
            nullable=False,
            server_default="NEW_CASE",
        ),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_applicant_submission_audit_applicant_id_applicants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("applicant_id", name=op.f("pk_applicant_submission_audit")),
    )


def downgrade() -> None:
    op.drop_table("applicant_submission_audit")
