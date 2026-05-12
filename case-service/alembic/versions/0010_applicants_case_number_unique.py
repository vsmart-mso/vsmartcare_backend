"""applicants.case_number: unique index สำหรับเลขคำร้องที่ระบบสร้าง

Revision ID: 0010_case_number_unique
Revises: 0009_current_status_cols
Create Date: 2026-05-12 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_case_number_unique"
down_revision: str | Sequence[str] | None = "0009_current_status_cols"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "uq_applicants_case_number",
        "applicants",
        ["case_number"],
        unique=True,
        postgresql_where=sa.text("case_number IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_applicants_case_number", table_name="applicants")
