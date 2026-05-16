"""update current_status dropdown none to wait

Revision ID: 0019_update_current_status_dropdown
Revises: 0018_payment_is037_nullable
Create Date: 2026-05-16 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_update_current_status_dropdown"
down_revision: str | Sequence[str] | None = "0018_payment_is037_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE current_status
            SET dropdown_to_change = 'รอรับเรื่อง'
            WHERE dropdown_to_change = 'none'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE current_status
            SET dropdown_to_change = 'none'
            WHERE dropdown_to_change = 'รอรับเรื่อง'
            """
        )
    )
