"""เพิ่ม responsible_division_id ใน case_handling สำหรับหน่วยงานรับผิดชอบ (vSmart Division.id)

Revision ID: 0074_case_handling_responsible_division
Revises: 0073_home_visit_fields
Create Date: 2026-07-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0074_case_handling_responsible_division"
down_revision = "0073_home_visit_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "case_handling",
        sa.Column("responsible_division_id", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("case_handling", "responsible_division_id")
