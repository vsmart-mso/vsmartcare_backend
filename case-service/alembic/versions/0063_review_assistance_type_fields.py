"""review_field: ปิด requested_assistance_detail, เพิ่ม 3 หัวข้อตีกลับแยก เงิน/สิ่งของ/อื่นๆ

Revision ID: 0063_review_assistance_type_fields
Revises: 0062_review_field_household_members
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0063_review_assistance_type_fields"
down_revision: str | Sequence[str] | None = "0062_review_field_household_members"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_FIELDS: list[dict] = [
    {
        "id": 46,
        "name": "requested_assistance_money",
        "label": "ช่วยเหลือเป็นเงิน",
        "step": 3,
        "display_order": 2,
    },
    {
        "id": 47,
        "name": "requested_assistance_in_kind",
        "label": "ช่วยเหลือเป็นสิ่งของ",
        "step": 3,
        "display_order": 3,
    },
    {
        "id": 48,
        "name": "requested_assistance_other",
        "label": "ช่วยเหลือเรื่องอื่นๆ",
        "step": 3,
        "display_order": 4,
    },
]


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            "UPDATE review_field SET is_active = false "
            "WHERE name = 'requested_assistance_detail'"
        )
    )

    for row in _NEW_FIELDS:
        bind.execute(
            sa.text(
                "INSERT INTO review_field (id, name, label, step, display_order, is_active) "
                "VALUES (:id, :name, :label, :step, :display_order, true) "
                "ON CONFLICT (id) DO UPDATE SET "
                "  name = EXCLUDED.name, "
                "  label = EXCLUDED.label, "
                "  step = EXCLUDED.step, "
                "  display_order = EXCLUDED.display_order, "
                "  is_active = EXCLUDED.is_active"
            ),
            row,
        )


def downgrade() -> None:
    bind = op.get_bind()

    for row in _NEW_FIELDS:
        bind.execute(
            sa.text("DELETE FROM review_field WHERE id = :id"),
            {"id": row["id"]},
        )

    bind.execute(
        sa.text(
            "UPDATE review_field SET is_active = true "
            "WHERE name = 'requested_assistance_detail'"
        )
    )
