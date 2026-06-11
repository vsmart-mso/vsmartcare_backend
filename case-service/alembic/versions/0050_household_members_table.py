"""สร้างตาราง household_members สำหรับเก็บข้อมูลสมาชิกในครัวเรือนแบบละเอียด (ปสค.๒)

Revision ID: 0050_household_members_table
Revises: 0049_pmj_reject_reason
Create Date: 2026-06-10 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0050_household_members_table"
down_revision: str | Sequence[str] | None = "0049_pmj_reject_reason"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "household_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False, comment="ลำดับสมาชิกในครัวเรือน"),
        sa.Column("national_id", sa.String(length=13), nullable=True, comment="เลขบัตรประชาชน (ถ้ามี)"),
        sa.Column("prefix_id", sa.Integer(), nullable=True, comment="FK → prefix_type"),
        sa.Column("prefix_other", sa.String(length=50), nullable=True, comment="คำนำหน้าอื่นๆ"),
        sa.Column("first_name", sa.String(length=255), nullable=False, comment="ชื่อ"),
        sa.Column("last_name", sa.String(length=255), nullable=False, comment="สกุล"),
        sa.Column("age", sa.Integer(), nullable=False, comment="อายุ"),
        sa.Column("relation_to_applicant", sa.String(length=100), nullable=True, comment="ความสัมพันธ์กับผู้ประสบปัญหา"),
        sa.Column("occupation", sa.String(length=255), nullable=True, comment="อาชีพ"),
        sa.Column("monthly_income", sa.Numeric(12, 2), nullable=True, comment="รายได้/เดือน (บาท)"),
        sa.Column("physical_condition", sa.String(length=20), nullable=False, server_default="normal", comment="สภาพทางร่างกาย: normal/disabled/chronic_illness"),
        sa.Column("self_care", sa.Boolean(), nullable=False, server_default=sa.text("true"), comment="ช่วยเหลือตนเองได้: true=ได้ / false=ไม่ได้"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_household_members_applicant_id_applicants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["prefix_id"],
            ["prefix_type.id"],
            name=op.f("fk_household_members_prefix_id_prefix_type"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_household_members")),
        sa.UniqueConstraint("applicant_id", "seq", name=op.f("uq_household_members_applicant_seq")),
    )
    op.create_index(
        op.f("ix_household_members_applicant_id"),
        "household_members",
        ["applicant_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_household_members_applicant_id"), table_name="household_members")
    op.drop_table("household_members")
