"""add หมายเหตุเพิ่มเติม to review_field master data

Revision ID: 0031_add_remarks_review_field
Revises: 0030_review_field_and_comment
Create Date: 2026-05-18 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031_add_remarks_review_field"
down_revision: str | Sequence[str] | None = "0030_review_field_and_comment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "INSERT INTO review_field (id, name, label, step, display_order, is_active) "
            "VALUES (43, 'remarks', 'หมายเหตุเพิ่มเติม', 4, 9, true) "
            "ON CONFLICT (id) DO UPDATE SET "
            "name = EXCLUDED.name, label = EXCLUDED.label, "
            "step = EXCLUDED.step, display_order = EXCLUDED.display_order, "
            "is_active = EXCLUDED.is_active"
        )
    )
    op.execute(
        sa.text(
            "SELECT setval(pg_get_serial_sequence('review_field', 'id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM review_field))"
        )
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM review_field WHERE id = 43")
    )
