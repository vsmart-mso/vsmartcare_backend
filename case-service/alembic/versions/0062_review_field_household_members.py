"""review_field: เปลี่ยน family_members_count → household_members (ปสค.๒)

เดิม label "จำนวนสมาชิกในครอบครัว (คน)" สะท้อนฟอร์มเก่าที่กรอกแค่ตัวเลข
หลัง TASK-07 ประชาชนแก้ไขรายละเอียดสมาชิกในตาราง — VSmart ต้องแสดงหัวข้อตีกลับให้ตรง

Revision ID: 0062_review_field_household_members
Revises: 0061_deactivate_regulations_56_57
Create Date: 2026-06-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0062_review_field_household_members"
down_revision: str | Sequence[str] | None = "0061_deactivate_regulations_56_57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE review_field "
            "SET name = 'household_members', label = 'ข้อมูลสมาชิกในครัวเรือน' "
            "WHERE id = 18"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE review_field "
            "SET name = 'family_members_count', label = 'จำนวนสมาชิกในครอบครัว (คน)' "
            "WHERE id = 18"
        )
    )
