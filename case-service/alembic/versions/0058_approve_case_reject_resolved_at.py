"""approve_case: add reject_resolved_at for PMJ reject lifecycle

Revision ID: 0058_approve_case_reject_resolved_at
Revises: 0057_review_field_ktb_fix_id
Create Date: 2026-06-12
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0058_approve_case_reject_resolved_at"
down_revision: str | Sequence[str] | None = "0057_review_field_ktb_fix_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "approve_case",
        sa.Column("reject_resolved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("approve_case", "reject_resolved_at")
