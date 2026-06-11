"""แก้ step ของ review_field ที่คลาดเคลื่อน

- bank_book_photo (id=34): step 3 → step 4  (UI ย้ายไป Step4 Documents แล้ว)

Revision ID: 0052_fix_review_field_steps
Revises: 0051_welfare_req_in_kind_text
Create Date: 2026-06-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0052_fix_review_field_steps"
down_revision: str | Sequence[str] | None = "0051_welfare_req_in_kind_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE review_field SET step = 4 WHERE name = 'bank_book_photo'")
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE review_field SET step = 3 WHERE name = 'bank_book_photo'")
    )
