"""แทนที่ column age (INT NOT NULL) ด้วย date_of_birth (DATE NULL) ใน household_members

อายุเป็น derived value คำนวณจาก date_of_birth ไม่ควรเก็บซ้ำ

Revision ID: 0054_household_member_dob
Revises: 0053_household_member_relation_type
Create Date: 2026-06-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0054_household_member_dob"
down_revision: str | Sequence[str] | None = "0053_household_member_relation_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "household_members",
        sa.Column(
            "date_of_birth",
            sa.Date(),
            nullable=True,
            comment="วันเกิด — อายุคำนวณจาก field นี้ ไม่เก็บในฐานข้อมูล",
        ),
    )
    op.drop_column("household_members", "age")


def downgrade() -> None:
    op.add_column(
        "household_members",
        sa.Column(
            "age",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="อายุ (ปี)",
        ),
    )
    op.drop_column("household_members", "date_of_birth")
