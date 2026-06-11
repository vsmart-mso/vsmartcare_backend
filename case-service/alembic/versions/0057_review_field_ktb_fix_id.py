"""review_field: แก้ conflict ID 43 — เปลี่ยนเป็น remarks + เพิ่ม doc_ktb_corporate ที่ ID 45

Migration 0056 ใช้ ID 43 สำหรับ doc_ktb_corporate ซึ่ง conflict กับ VSmart
ที่ hardcode _STANDALONE_FIELD_IDS = {43} ไว้สำหรับ "หมายเหตุเพิ่มเติม"

แก้:
- ID 43 → remarks (หมายเหตุเพิ่มเติม, step=0) เพื่อรองรับ VSmart standalone section
- ID 45 → doc_ktb_corporate (step=4, display_order=10)

Revision ID: 0057_review_field_ktb_fix_id
Revises: 0056_review_field_ktb
Create Date: 2026-06-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0057_review_field_ktb_fix_id"
down_revision: str | Sequence[str] | None = "0056_review_field_ktb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    # เปลี่ยน ID 43 เป็น remarks สำหรับ VSmart standalone section
    bind.execute(
        sa.text(
            "UPDATE review_field SET name='remarks', label='หมายเหตุเพิ่มเติม', step=0, display_order=99 "
            "WHERE id = 43"
        )
    )
    # เพิ่ม doc_ktb_corporate ที่ ID 45 (step=4, display_order=10)
    bind.execute(
        sa.text(
            "INSERT INTO review_field (id, name, label, step, display_order, is_active) "
            "VALUES (45, 'doc_ktb_corporate', 'รูปแบบฟอร์ม KTB Corporate Online', 4, 10, true) "
            "ON CONFLICT (id) DO UPDATE SET name=EXCLUDED.name, label=EXCLUDED.label, "
            "step=EXCLUDED.step, display_order=EXCLUDED.display_order, is_active=EXCLUDED.is_active"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM review_field WHERE id = 45"))
    bind.execute(
        sa.text(
            "UPDATE review_field SET name='doc_ktb_corporate', "
            "label='รูปแบบฟอร์ม KTB Corporate Online', step=4, display_order=9 "
            "WHERE id = 43"
        )
    )
