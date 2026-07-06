"""review_field: ปิดใช้งาน doc_ktb_corporate (ID 45)

Revision ID: 0075_review_field_disable_ktb_corporate
Revises: 0074_case_handling_responsible_division
Create Date: 2026-07-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0075_review_field_disable_ktb_corporate"
down_revision: str | Sequence[str] | None = "0074_case_handling_responsible_division"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE review_field SET is_active = false WHERE id = 45"))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE review_field SET is_active = true WHERE id = 45"))
