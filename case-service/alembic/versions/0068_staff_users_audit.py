"""staff_users + security_audit_log (HI-01, CR-05)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0068_staff_users_audit"
down_revision = "0067_article_approver_sdhsv_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "staff_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=200), server_default="", nullable=False),
        sa.Column("province_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["province_id"], ["province.id"], name=op.f("fk_staff_users_province_id_province")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_staff_users")),
        sa.UniqueConstraint("username", name=op.f("uq_staff_users_username")),
    )
    op.create_index(op.f("ix_staff_users_province_id"), "staff_users", ["province_id"], unique=False)

    op.create_table(
        "security_audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("target_cid", sa.String(length=13), nullable=True),
        sa.Column("detail", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_audit_log")),
    )
    op.create_index(op.f("ix_security_audit_log_action"), "security_audit_log", ["action"], unique=False)
    op.create_index(op.f("ix_security_audit_log_target_cid"), "security_audit_log", ["target_cid"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_security_audit_log_target_cid"), table_name="security_audit_log")
    op.drop_index(op.f("ix_security_audit_log_action"), table_name="security_audit_log")
    op.drop_table("security_audit_log")
    op.drop_index(op.f("ix_staff_users_province_id"), table_name="staff_users")
    op.drop_table("staff_users")
