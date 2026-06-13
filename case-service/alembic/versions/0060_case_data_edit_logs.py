"""สร้าง case_data_edit_logs + ย้าย audit แก้ไขข้อมูลออกจาก welfare_request_status

Revision ID: 0060_case_data_edit_logs
Revises: 0059_admin_province_access
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0060_case_data_edit_logs"
down_revision: str | Sequence[str] | None = "0059_admin_province_access"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "case_data_edit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("current_status_id_at_edit", sa.Integer(), nullable=False),
        sa.Column("edit_by_sdshv", sa.String(length=255), nullable=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("sections", sa.String(length=32), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_case_data_edit_logs_applicant_id_applicants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["current_status_id_at_edit"],
            ["current_status.id"],
            name=op.f(
                "fk_case_data_edit_logs_current_status_id_at_edit_current_status"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_data_edit_logs")),
    )
    op.create_index(
        op.f("ix_case_data_edit_logs_applicant_id"),
        "case_data_edit_logs",
        ["applicant_id"],
        unique=False,
    )

    # ย้าย audit ที่เคยบันทึกใน welfare_request_status (remarks ขึ้นต้น "นักสังคมฯ แก้ไข")
    op.execute(
        sa.text(
            """
            INSERT INTO case_data_edit_logs (
                created_at,
                applicant_id,
                current_status_id_at_edit,
                edit_by_sdshv,
                event_type,
                sections,
                remarks
            )
            SELECT
                COALESCE(wrs.updated_at, wrs.created_at),
                wrs.applicant_id,
                wrs.current_status_id,
                wrs.update_by_sdshv,
                CASE
                    WHEN wrs.remarks LIKE '%ผลการเยี่ยมบ้าน%' THEN 'survey_edit'
                    ELSE 'section_edit'
                END,
                NULL,
                wrs.remarks
            FROM welfare_request_status wrs
            WHERE wrs.remarks LIKE 'นักสังคมฯ แก้ไข%'
            """
        )
    )
    op.execute(
        sa.text(
            """
            DELETE FROM welfare_request_status
            WHERE remarks LIKE 'นักสังคมฯ แก้ไข%'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO welfare_request_status (
                created_at,
                updated_at,
                applicant_id,
                current_status_id,
                update_by_sdshv,
                remarks
            )
            SELECT
                c.created_at,
                c.created_at,
                c.applicant_id,
                c.current_status_id_at_edit,
                c.edit_by_sdshv,
                c.remarks
            FROM case_data_edit_logs c
            """
        )
    )
    op.drop_index(
        op.f("ix_case_data_edit_logs_applicant_id"),
        table_name="case_data_edit_logs",
    )
    op.drop_table("case_data_edit_logs")
