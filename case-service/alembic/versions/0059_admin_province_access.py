"""admin_users + province_access_config — ควบคุมเปิด/ปิดบริการรายจังหวัด (TASK-v-care-12062026-01)

- admin_users: บัญชี admin (สมัครผ่าน CLI เท่านั้น — ไม่มี UI signup), password เป็น bcrypt hash
- province_access_config: 1 จังหวัด 1 แถว, is_enabled default false (default deny — ทยอยเปิด)

Revision ID: 0059_admin_province_access
Revises: 0058_approve_case_reject_resolved_at
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0059_admin_province_access"
down_revision: str | Sequence[str] | None = "0058_approve_case_reject_resolved_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False, comment="ชื่อผู้ใช้งาน admin"),
        sa.Column("password_hash", sa.String(length=255), nullable=False, comment="bcrypt hash"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_users")),
        sa.UniqueConstraint("username", name=op.f("uq_admin_users_username")),
    )

    op.create_table(
        "province_access_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("province_id", sa.Integer(), nullable=False, comment="FK → province (1 จังหวัด 1 แถว)"),
        sa.Column(
            "is_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="true=เปิดรับบันทึกข้อมูล / false=ปิด (default deny)",
        ),
        sa.Column("updated_by_admin_id", sa.Integer(), nullable=True, comment="admin คนล่าสุดที่แก้ไข"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["province_id"],
            ["province.id"],
            name=op.f("fk_province_access_config_province_id_province"),
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_admin_id"],
            ["admin_users.id"],
            name=op.f("fk_province_access_config_updated_by_admin_id_admin_users"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_province_access_config")),
        sa.UniqueConstraint("province_id", name=op.f("uq_province_access_config_province_id")),
    )


def downgrade() -> None:
    op.drop_table("province_access_config")
    op.drop_table("admin_users")
