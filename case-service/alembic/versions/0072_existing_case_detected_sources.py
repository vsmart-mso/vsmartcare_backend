"""existing_case_detected_sources — แหล่งที่พบรายเดิมตอน snapshot

Revision ID: 0072_existing_case_detected_sources
Revises: 0071_applicant_submission_audit
Create Date: 2026-07-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0072_existing_case_detected_sources"
down_revision: str | None = "0071_applicant_submission_audit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "applicant_submission_audit",
        sa.Column("existing_case_detected_sources", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("applicant_submission_audit", "existing_case_detected_sources")
