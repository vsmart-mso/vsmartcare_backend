"""economic_infos: เพิ่ม column housing_types_rent (ค่าเช่าต่อเดือน)

Revision ID: 0024_economic_housing_rent
Revises: 0023_address_add_alley
Create Date: 2026-05-17 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_economic_housing_rent"
down_revision: str | Sequence[str] | None = "0023_address_add_alley"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "economic_infos",
        sa.Column(
            "housing_types_rent",
            sa.Numeric(12, 2),
            nullable=True,
            comment="ค่าเช่าต่อเดือน (บาท) — กรอกเมื่อ housing_types เป็นบ้านเช่า",
        ),
    )


def downgrade() -> None:
    op.drop_column("economic_infos", "housing_types_rent")
