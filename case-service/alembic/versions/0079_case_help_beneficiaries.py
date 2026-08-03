"""สร้างตาราง case_help_beneficiaries สำหรับผู้รับความช่วยเหลือหน้า 11

Revision ID: 0079_case_help_beneficiaries
Revises: 0078_attachment_cash_proof
Create Date: 2026-08-03
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0079_case_help_beneficiaries"
down_revision: str | Sequence[str] | None = "0078_attachment_cash_proof"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "case_help_beneficiaries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_handling_id", sa.Integer(), nullable=False),
        sa.Column(
            "household_member_id",
            sa.Integer(),
            nullable=True,
            comment="FK → household_members.id; NULL = ผู้ยื่น",
        ),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("national_id", sa.String(length=13), nullable=True),
        sa.Column("age_years", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_handling_id"],
            ["case_handling.id"],
            name=op.f("fk_case_help_beneficiaries_case_handling_id_case_handling"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["household_member_id"],
            ["household_members.id"],
            name=op.f("fk_case_help_beneficiaries_household_member_id_household_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_help_beneficiaries")),
    )
    op.create_index(
        op.f("ix_case_help_beneficiaries_case_handling_id"),
        "case_help_beneficiaries",
        ["case_handling_id"],
    )
    op.create_index(
        op.f("ix_case_help_beneficiaries_household_member_id"),
        "case_help_beneficiaries",
        ["household_member_id"],
    )
    op.create_index(
        "uq_case_help_beneficiaries_handling_member",
        "case_help_beneficiaries",
        ["case_handling_id", "household_member_id"],
        unique=True,
        postgresql_where=sa.text("household_member_id IS NOT NULL"),
    )
    op.create_index(
        "uq_case_help_beneficiaries_handling_applicant",
        "case_help_beneficiaries",
        ["case_handling_id"],
        unique=True,
        postgresql_where=sa.text("household_member_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_case_help_beneficiaries_handling_applicant",
        table_name="case_help_beneficiaries",
    )
    op.drop_index(
        "uq_case_help_beneficiaries_handling_member",
        table_name="case_help_beneficiaries",
    )
    op.drop_index(
        op.f("ix_case_help_beneficiaries_household_member_id"),
        table_name="case_help_beneficiaries",
    )
    op.drop_index(
        op.f("ix_case_help_beneficiaries_case_handling_id"),
        table_name="case_help_beneficiaries",
    )
    op.drop_table("case_help_beneficiaries")
