"""applicants: process_completed_at — หยุดนับ SLA เมื่อสถานะ 4 หรือ 10

Revision ID: 0047_applicant_process_completed_at
Revises: 0046_article_and_approve_case_article_id
Create Date: 2026-05-26 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0047_applicant_process_completed_at"
down_revision: str | Sequence[str] | None = "0046_article_and_approve_case_article_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "applicants",
        sa.Column("process_completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applicants", "process_completed_at")
