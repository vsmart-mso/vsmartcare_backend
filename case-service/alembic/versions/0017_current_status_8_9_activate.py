"""current_status id 8–9: เปิด dropdown_activate และ filter_activate

Revision ID: 0017_current_status_8_9_activate
Revises: 0016_approve_case_esignature_text
Create Date: 2026-05-15 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_current_status_8_9_activate"
down_revision: str | Sequence[str] | None = "0016_approve_esignature_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE current_status
            SET dropdown_activate = TRUE, filter_activate = TRUE
            WHERE id IN (8, 9)
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE current_status
            SET dropdown_activate = FALSE, filter_activate = FALSE
            WHERE id IN (8, 9)
            """
        )
    )
