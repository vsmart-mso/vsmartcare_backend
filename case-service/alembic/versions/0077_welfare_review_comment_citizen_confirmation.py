"""welfare_review_comment: citizen confirmation flags (TASK_211)

บันทึกว่าประชาชนยืนยันฟิลด์ที่ถูกตีกลับแล้วเมื่อไหร่ และยืนยันแบบไหน
(unchanged_ok | edited) ตอน POST /v1/cases/{id}/resubmit — หลักฐานตาม BR-8

Revision ID: 0077_welfare_review_comment_citizen_confirmation
Revises: 0076_persons_province_id
Create Date: 2026-07-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0077_welfare_review_comment_citizen_confirmation"
down_revision: str | Sequence[str] | None = "0076_persons_province_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "welfare_review_comment",
        sa.Column(
            "citizen_confirmed_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="เวลาที่ประชาชนยืนยันฟิลด์นี้ตอน resubmit (TASK_211)",
        ),
    )
    op.add_column(
        "welfare_review_comment",
        sa.Column(
            "citizen_confirmation_type",
            sa.String(length=20),
            nullable=True,
            comment="unchanged_ok | edited — ประเภทการยืนยันตอน resubmit (TASK_211)",
        ),
    )


def downgrade() -> None:
    op.drop_column("welfare_review_comment", "citizen_confirmation_type")
    op.drop_column("welfare_review_comment", "citizen_confirmed_at")
