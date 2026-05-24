"""เพิ่ม deposit_type / branch_name / branch_code ใน ocr_results (OCR อ่านเพิ่ม).

Revision ID: 0041_ocr_bank_extra_fields
Revises: 0040_satisfaction_survey_cascade
Create Date: 2026-05-24 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041_ocr_bank_extra_fields"
down_revision: str | Sequence[str] | None = "0040_satisfaction_survey_cascade"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # เก็บ nullable เสมอ — OCR คืน null ได้เมื่ออ่านไม่ได้ การ "บังคับ" ทำที่ชั้น UI
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("ocr_results")}

    if "deposit_type" not in existing:
        op.add_column("ocr_results", sa.Column("deposit_type", sa.Text(), nullable=True))
    if "branch_name" not in existing:
        op.add_column("ocr_results", sa.Column("branch_name", sa.Text(), nullable=True))
    if "branch_code" not in existing:
        op.add_column("ocr_results", sa.Column("branch_code", sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column("ocr_results", "branch_code")
    op.drop_column("ocr_results", "branch_name")
    op.drop_column("ocr_results", "deposit_type")
