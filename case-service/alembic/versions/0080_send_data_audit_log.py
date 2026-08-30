"""เพิ่ม audit + snapshot columns ใน send_data สำหรับ MSO forward log

Revision ID: 0080_send_data_audit_log
Revises: 0079_case_help_beneficiaries
Create Date: 2026-08-29

Backfill แถวเก่า: created_at / updated_at = now() ตอน migrate (ไม่มีแหล่ง timestamp เดิม)
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0080_send_data_audit_log"
down_revision: str | Sequence[str] | None = "0079_case_help_beneficiaries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "send_data",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column(
        "send_data",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.add_column("send_data", sa.Column("ip_address", sa.String(length=45), nullable=True))
    op.add_column("send_data", sa.Column("user_agent", sa.String(length=500), nullable=True))
    op.add_column("send_data", sa.Column("request_url", sa.String(length=2048), nullable=True))
    op.add_column("send_data", sa.Column("device", sa.String(length=64), nullable=True))
    op.add_column("send_data", sa.Column("browser", sa.String(length=64), nullable=True))
    op.add_column("send_data", sa.Column("browser_version", sa.String(length=32), nullable=True))
    op.add_column("send_data", sa.Column("os", sa.String(length=64), nullable=True))
    op.add_column("send_data", sa.Column("os_version", sa.String(length=32), nullable=True))
    op.add_column("send_data", sa.Column("type_money_category_id", sa.Integer(), nullable=True))
    op.add_column("send_data", sa.Column("type_money_name", sa.String(length=255), nullable=True))
    op.add_column("send_data", sa.Column("type_money_acronym", sa.String(length=255), nullable=True))
    op.add_column("send_data", sa.Column("province_id", sa.Integer(), nullable=True))
    op.add_column("send_data", sa.Column("province_name", sa.String(length=255), nullable=True))
    op.add_column("send_data", sa.Column("affected_person_name", sa.String(length=511), nullable=True))
    op.add_column("send_data", sa.Column("affected_person_cid", sa.String(length=13), nullable=True))

    op.create_foreign_key(
        op.f("fk_send_data_type_money_category_id_type_money_category"),
        "send_data",
        "type_money_category",
        ["type_money_category_id"],
        ["id"],
    )
    op.create_foreign_key(
        op.f("fk_send_data_province_id_province"),
        "send_data",
        "province",
        ["province_id"],
        ["id"],
    )
    op.create_index(
        "ix_send_data_province_id_created_at",
        "send_data",
        ["province_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_send_data_province_id_created_at", table_name="send_data")
    op.drop_constraint(
        op.f("fk_send_data_province_id_province"),
        "send_data",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_send_data_type_money_category_id_type_money_category"),
        "send_data",
        type_="foreignkey",
    )
    op.drop_column("send_data", "affected_person_cid")
    op.drop_column("send_data", "affected_person_name")
    op.drop_column("send_data", "province_name")
    op.drop_column("send_data", "province_id")
    op.drop_column("send_data", "type_money_acronym")
    op.drop_column("send_data", "type_money_name")
    op.drop_column("send_data", "type_money_category_id")
    op.drop_column("send_data", "os_version")
    op.drop_column("send_data", "os")
    op.drop_column("send_data", "browser_version")
    op.drop_column("send_data", "browser")
    op.drop_column("send_data", "device")
    op.drop_column("send_data", "request_url")
    op.drop_column("send_data", "user_agent")
    op.drop_column("send_data", "ip_address")
    op.drop_column("send_data", "updated_at")
    op.drop_column("send_data", "created_at")
