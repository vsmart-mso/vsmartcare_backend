"""approve_case: add approval_superseded_at for reopen soft-supersede

Revision ID: 0082_approve_case_approval_superseded_at
Revises: 0081_liveness_attempts
Create Date: 2026-09-12
"""

from __future__ import annotations

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0081_approve_case_approval_superseded_at"
down_revision: str | Sequence[str] | None = "0080_send_data_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "approve_case",
        sa.Column("approval_superseded_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("approve_case", "approval_superseded_at")
