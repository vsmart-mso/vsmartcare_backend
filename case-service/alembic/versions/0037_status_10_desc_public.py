"""อัปเดต current_status id=10 description_public เป็น 'เบิกจ่ายสำเร็จ'.

Revision ID: 0037_status_10_desc_public
Revises: 0036_satisfaction_survey
Create Date: 2026-05-19 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037_status_10_desc_public"
down_revision: str | Sequence[str] | None = "0036_satisfaction_survey"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE current_status SET description_public = 'เบิกจ่ายสำเร็จ' WHERE id = 10"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE current_status SET description_public = NULL WHERE id = 10"
        )
    )
