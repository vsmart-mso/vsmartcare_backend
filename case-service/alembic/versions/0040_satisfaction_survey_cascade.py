"""เพิ่ม ON DELETE CASCADE ให้ fk_satisfaction_surveys_applicant_id.

Revision ID: 0040_satisfaction_survey_cascade
Revises: 0039_review_bank_aid_changes
Create Date: 2026-05-20 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0040_satisfaction_survey_cascade"
down_revision: str | Sequence[str] | None = "0039_review_bank_aid_changes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_FK_NAME = "fk_satisfaction_surveys_applicant_id"


def upgrade() -> None:
    op.drop_constraint(_FK_NAME, "satisfaction_surveys", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        "satisfaction_surveys",
        "applicants",
        ["applicant_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint(_FK_NAME, "satisfaction_surveys", type_="foreignkey")
    op.create_foreign_key(
        _FK_NAME,
        "satisfaction_surveys",
        "applicants",
        ["applicant_id"],
        ["id"],
    )
