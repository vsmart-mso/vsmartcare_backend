"""ปิด activate ระเบียบ id 56, 57 (สค. เงินค่าแรงงานสตรี + รวมกลุ่มประกอบอาชีพ)

Revision ID: 0061_deactivate_regulations_56_57
Revises: 0060_case_data_edit_logs
Create Date: 2026-06-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0061_deactivate_regulations_56_57"
down_revision: str | Sequence[str] | None = "0060_case_data_edit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REGULATION_IDS = (56, 57)


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE announcement_regulations SET activate = FALSE"
            " WHERE id = ANY(:ids)"
        ).bindparams(ids=list(_REGULATION_IDS))
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE announcement_regulations SET activate = TRUE"
            " WHERE id = ANY(:ids)"
        ).bindparams(ids=list(_REGULATION_IDS))
    )
