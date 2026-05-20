"""สร้างตาราง satisfaction_surveys — เก็บผลประเมินความพึงพอใจของผู้ยื่นคำขอ.

Revision ID: 0036_satisfaction_survey
Revises: 0034_upload_batch_id
Create Date: 2026-05-19 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036_satisfaction_survey"
down_revision: str | Sequence[str] | None = "0034_upload_batch_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            CREATE TABLE IF NOT EXISTS satisfaction_surveys (
                id          SERIAL          NOT NULL,
                applicant_id INTEGER        NOT NULL,
                survey_type  VARCHAR(50)    NOT NULL,
                rating       INTEGER        NOT NULL CHECK (rating BETWEEN 1 AND 5),
                comment      TEXT,
                created_at   TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT now(),
                CONSTRAINT pk_satisfaction_surveys PRIMARY KEY (id),
                CONSTRAINT fk_satisfaction_surveys_applicant_id
                    FOREIGN KEY (applicant_id) REFERENCES applicants (id) ON DELETE CASCADE
            )
            """
        )
    )

    bind.execute(
        sa.text(
            "CREATE INDEX IF NOT EXISTS ix_satisfaction_surveys_applicant_id "
            "ON satisfaction_surveys (applicant_id)"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DROP TABLE IF EXISTS satisfaction_surveys"))
