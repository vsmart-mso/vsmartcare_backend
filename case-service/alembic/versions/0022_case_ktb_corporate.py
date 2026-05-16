"""payment intake v2: case_ktb_corporate (หน้า 20 — KTB Corporate Online)

Revision ID: 0022_case_ktb_corporate
Revises: 0021_payment_method_case_payment
Create Date: 2026-05-16 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0022_case_ktb_corporate"
down_revision: str | Sequence[str] | None = "0021_payment_method_case_payment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

recipient_category_enum = postgresql.ENUM(
    "payroll",
    "gov_other",
    "external",
    name="ktb_recipient_category",
    create_type=False,
)
notify_channel_enum = postgresql.ENUM(
    "sms",
    "email",
    name="ktb_notify_channel",
    create_type=False,
)


def _create_enum_if_missing(enum_name: str, labels: tuple[str, ...]) -> None:
    labels_sql = ", ".join(f"'{label}'" for label in labels)
    op.execute(
        sa.text(
            f"""
            DO $$ BEGIN
                CREATE TYPE {enum_name} AS ENUM ({labels_sql});
            EXCEPTION
                WHEN duplicate_object THEN NULL;
            END $$;
            """
        )
    )


def upgrade() -> None:
    _create_enum_if_missing("ktb_recipient_category", ("payroll", "gov_other", "external"))
    _create_enum_if_missing("ktb_notify_channel", ("sms", "email"))

    op.create_table(
        "case_ktb_corporate",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_handling_id", sa.Integer(), nullable=False),
        sa.Column("form_number", sa.Integer(), nullable=True),
        sa.Column("director_division_ref", sa.String(length=500), nullable=True),
        sa.Column("paying_division_ref", sa.String(length=500), nullable=True),
        sa.Column(
            "recipient_category",
            recipient_category_enum,
            nullable=False,
        ),
        sa.Column("payroll_bank_name_id", sa.Integer(), nullable=True),
        sa.Column("payroll_bank_branch", sa.String(length=255), nullable=True),
        sa.Column("payroll_account_type", sa.String(length=100), nullable=True),
        sa.Column("payroll_account_number", sa.String(length=50), nullable=True),
        sa.Column("other_bank_name_id", sa.Integer(), nullable=True),
        sa.Column("other_bank_branch", sa.String(length=255), nullable=True),
        sa.Column("other_account_type", sa.String(length=100), nullable=True),
        sa.Column("other_account_number", sa.String(length=50), nullable=True),
        sa.Column("notify_channel", notify_channel_enum, nullable=True),
        sa.Column("notify_contact", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["case_handling_id"],
            ["case_handling.id"],
            name=op.f("fk_case_ktb_corporate_case_handling_id_case_handling"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["other_bank_name_id"],
            ["bank_name.id"],
            name=op.f("fk_case_ktb_corporate_other_bank_name_id_bank_name"),
        ),
        sa.ForeignKeyConstraint(
            ["payroll_bank_name_id"],
            ["bank_name.id"],
            name=op.f("fk_case_ktb_corporate_payroll_bank_name_id_bank_name"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_ktb_corporate")),
        sa.UniqueConstraint(
            "case_handling_id",
            name=op.f("uq_case_ktb_corporate_case_handling_id"),
        ),
    )
    op.create_index(
        op.f("ix_case_ktb_corporate_case_handling_id"),
        "case_ktb_corporate",
        ["case_handling_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_case_ktb_corporate_payroll_bank_name_id"),
        "case_ktb_corporate",
        ["payroll_bank_name_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_case_ktb_corporate_other_bank_name_id"),
        "case_ktb_corporate",
        ["other_bank_name_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_case_ktb_corporate_other_bank_name_id"),
        table_name="case_ktb_corporate",
    )
    op.drop_index(
        op.f("ix_case_ktb_corporate_payroll_bank_name_id"),
        table_name="case_ktb_corporate",
    )
    op.drop_index(
        op.f("ix_case_ktb_corporate_case_handling_id"),
        table_name="case_ktb_corporate",
    )
    op.drop_table("case_ktb_corporate")

    op.execute(sa.text("DROP TYPE IF EXISTS ktb_notify_channel"))
    op.execute(sa.text("DROP TYPE IF EXISTS ktb_recipient_category"))
