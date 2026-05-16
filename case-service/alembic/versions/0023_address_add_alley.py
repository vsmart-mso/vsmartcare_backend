"""address: เพิ่ม column alley (ตรอก) แยกจาก sub_lane (ซอย)

Revision ID: 0023_address_add_alley
Revises: 0022_case_ktb_corporate
Create Date: 2026-05-16 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_address_add_alley"
down_revision: str | Sequence[str] | None = "0022_case_ktb_corporate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "address",
        sa.Column("alley", sa.String(length=255), nullable=True, comment="ตรอก"),
    )


def downgrade() -> None:
    op.drop_column("address", "alley")
