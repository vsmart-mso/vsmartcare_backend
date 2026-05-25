"""welfare_payment reject history: created_at, 037 lock index, file_payment FK

Revision ID: 0033_welfare_payment_reject
Revises: 0032_bank_acct_type_fix
Create Date: 2026-05-18 14:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033_welfare_payment_reject"
down_revision: str | Sequence[str] | None = "0032_bank_acct_type_fix"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UQ_037_PER_DDA = "uq_welfare_payment_applicant_dda_037"
IX_PAYMENT_APPLICANT_DDA_TYPE = "ix_welfare_payment_applicant_dda_type"
FK_FILE_PAYMENT_WELFARE_PAYMENT = "fk_file_payment_welfare_payment_id_welfare_payment"
IX_FILE_PAYMENT_WELFARE_PAYMENT = "ix_file_payment_welfare_payment_id"


def upgrade() -> None:
    op.add_column(
        "welfare_payment",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        UQ_037_PER_DDA,
        "welfare_payment",
        ["applicant_id", "dda_ref_id"],
        unique=True,
        postgresql_where=sa.text("is_037_or_038 IS FALSE"),
    )
    op.create_index(
        IX_PAYMENT_APPLICANT_DDA_TYPE,
        "welfare_payment",
        ["applicant_id", "dda_ref_id", "is_037_or_038"],
        unique=False,
    )
    op.add_column(
        "file_payment",
        sa.Column("welfare_payment_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        FK_FILE_PAYMENT_WELFARE_PAYMENT,
        "file_payment",
        "welfare_payment",
        ["welfare_payment_id"],
        ["id"],
    )
    op.create_index(
        IX_FILE_PAYMENT_WELFARE_PAYMENT,
        "file_payment",
        ["welfare_payment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(IX_FILE_PAYMENT_WELFARE_PAYMENT, table_name="file_payment")
    op.drop_constraint(FK_FILE_PAYMENT_WELFARE_PAYMENT, "file_payment", type_="foreignkey")
    op.drop_column("file_payment", "welfare_payment_id")
    op.drop_index(IX_PAYMENT_APPLICANT_DDA_TYPE, table_name="welfare_payment")
    op.drop_index(UQ_037_PER_DDA, table_name="welfare_payment")
    op.drop_column("welfare_payment", "created_at")
