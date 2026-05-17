"""applicants: process_started_at, process_sla_days for SLA countdown

Revision ID: 0027_applicant_process_sla
Revises: 0027_bank_account_type
Create Date: 2026-05-17 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027_applicant_process_sla"
down_revision: str | Sequence[str] | None = "0027_bank_account_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "applicants",
        sa.Column("process_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "applicants",
        sa.Column("process_sla_days", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applicants", "process_sla_days")
    op.drop_column("applicants", "process_started_at")
