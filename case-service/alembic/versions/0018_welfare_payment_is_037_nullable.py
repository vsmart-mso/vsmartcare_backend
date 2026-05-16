"""welfare_payment is_037_or_038 nullable until payment process sets it

Revision ID: 0018_payment_is037_nullable
Revises: 0017_current_status_8_9_activate
Create Date: 2026-05-16 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_payment_is037_nullable"
down_revision: str | Sequence[str] | None = "0017_current_status_8_9_activate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "welfare_payment",
        "is_037_or_038",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=None,
    )
    op.execute(
        sa.text(
            """
            UPDATE welfare_payment
            SET is_037_or_038 = NULL
            WHERE is_037_or_038 = false
              AND payment_number IS NULL
              AND payment_038_reason IS NULL
              AND transaction_date IS NULL
              AND effective_date IS NULL
              AND user_sdshv IS NULL
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE welfare_payment
            SET is_037_or_038 = false
            WHERE is_037_or_038 IS NULL
            """
        )
    )
    op.alter_column(
        "welfare_payment",
        "is_037_or_038",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
