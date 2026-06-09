"""approve_case: add reject_reason for PMJ rejection

Revision ID: 0049_pmj_reject_reason
Revises: 0048_current_status_id_11
Create Date: 2026-06-09 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049_pmj_reject_reason"
down_revision: str | Sequence[str] | None = "0048_current_status_id_11"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("approve_case", sa.Column("reject_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("approve_case", "reject_reason")
