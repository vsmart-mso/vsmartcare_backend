"""สถานะความเดือดร้อน: สร้างตาราง master hardship_status_types + seed 2 แถว
และเพิ่มคอลัมน์ screening_logs.hardship_status_ids (JSON) เก็บ id ที่ผู้ใช้เลือก

Revision ID: 0064_hardship_status_types
Revises: 0063_review_assistance_type_fields
Create Date: 2026-06-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0064_hardship_status_types"
down_revision: str | Sequence[str] | None = "0063_review_assistance_type_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# แถว master data ของสถานะความเดือดร้อน (เลือกได้หลายข้อในหน้าตรวจสอบสิทธิ์)
_SEED_ROWS: list[dict] = [
    {"id": 1, "name": "ประสบปัญหาความเดือดร้อน"},
    {"id": 2, "name": "ครอบครัวประสบปัญหาความเดือดร้อน"},
]


def upgrade() -> None:
    # 1) สร้างตาราง master hardship_status_types (โครงสร้าง id + name เหมือน lookup อื่น)
    op.create_table(
        "hardship_status_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_hardship_status_types")),
    )

    # 2) seed ข้อมูลตั้งต้น 2 แถว (idempotent ด้วย ON CONFLICT DO UPDATE)
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO hardship_status_types (id, name) VALUES (:id, :name) "
            "ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name"
        ),
        _SEED_ROWS,
    )

    # 3) เพิ่มคอลัมน์เก็บ id ที่ผู้ใช้เลือก ลงใน screening_logs (nullable — เคสเก่าไม่มีข้อมูล)
    op.add_column(
        "screening_logs",
        sa.Column("hardship_status_ids", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("screening_logs", "hardship_status_ids")
    op.drop_table("hardship_status_types")
