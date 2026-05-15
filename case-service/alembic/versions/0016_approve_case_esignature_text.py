"""alter approve_case esignature to text

Revision ID: 0016_approve_case_esignature_text
Revises: 0015_current_status_vsmart
Create Date: 2026-05-15 22:15:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_approve_case_esignature_text"
down_revision: str | Sequence[str] | None = "0015_current_status_vsmart"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "approve_case",
        "esignature",
        existing_type=sa.String(length=1024),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "approve_case",
        "esignature",
        existing_type=sa.Text(),
        type_=sa.String(length=1024),
        existing_nullable=True,
    )
