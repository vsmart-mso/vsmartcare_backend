"""persons: เพิ่ม province_id (FK → province) — TASK-v-care-12062026-01

จุดคำนวณจังหวัดจุดเดียว: thaid-auth-service resolve จากที่อยู่ ThaiD ตอน login
(person_persist.py::resolve_province_id_from_address) แล้วเก็บที่นี่ — submit gate
(services/province_access.py::is_province_enabled_by_person_id) อ่านคอลัมน์นี้ตรง ๆ
แทนการเดินลูกโซ่ sub_district_postcode_id → sub_district → district → province แบบเดิม
ซึ่งพังกับที่อยู่ที่ resolve sub_district_postcode_id ไม่สำเร็จ (เช่น กรุงเทพฯ, เมืองพัทยา)
ทำให้ gate ตอน login กับตอน submit อ่านค่าจังหวัดไม่ตรงกัน

Revision ID: 0076_persons_province_id
Revises: 0075_review_field_disable_ktb_corporate
Create Date: 2026-07-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0076_persons_province_id"
down_revision: str | Sequence[str] | None = "0075_review_field_disable_ktb_corporate"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "persons",
        sa.Column(
            "province_id",
            sa.Integer(),
            nullable=True,
            comment="จังหวัดที่ resolve จากที่อยู่ ThaiD ตอน login (TASK-v-care-12062026-01)",
        ),
    )
    op.create_index(op.f("ix_persons_province_id"), "persons", ["province_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_persons_province_id_province"),
        "persons",
        "province",
        ["province_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_persons_province_id_province"), "persons", type_="foreignkey")
    op.drop_index(op.f("ix_persons_province_id"), table_name="persons")
    op.drop_column("persons", "province_id")
