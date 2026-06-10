"""เพิ่มตาราง household_member_relation_types + FK ใน household_members + เพิ่ม prefix เด็กหญิง/เด็กชาย

การเปลี่ยนแปลง:
- สร้างตาราง household_member_relation_types (id, name) พร้อม seed 9 รายการ
- เพิ่ม column relation_to_applicant_id INT NULL FK → household_member_relation_types ใน household_members
- ลบ column relation_to_applicant VARCHAR(100) ออกจาก household_members
- เพิ่ม prefix_type: เด็กหญิง (id=4), เด็กชาย (id=5)

Revision ID: 0053_household_member_relation_type
Revises: 0052_fix_review_field_steps
Create Date: 2026-06-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0053_household_member_relation_type"
down_revision: str | Sequence[str] | None = "0052_fix_review_field_steps"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_RELATION_ROWS = [
    {"id": 1,  "name": "บิดา/มารดา"},
    {"id": 2,  "name": "ญาติพี่น้อง"},
    {"id": 3,  "name": "บุตร"},
    {"id": 4,  "name": "คู่สมรส"},
    {"id": 5,  "name": "เจ้าหน้าที่จาก อบต."},
    {"id": 6,  "name": "ผู้ใหญ่บ้าน"},
    {"id": 7,  "name": "เหลน"},
    {"id": 8,  "name": "หลาน"},
    {"id": 9,  "name": "ทวด"},
]

_PREFIX_EXTRA = [
    {"id": 4, "name": "เด็กหญิง"},
    {"id": 5, "name": "เด็กชาย"},
]


def upgrade() -> None:
    # ── สร้างตาราง household_member_relation_types ──────────────────────────────
    op.create_table(
        "household_member_relation_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_household_member_relation_types")),
    )

    # seed ข้อมูล
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO household_member_relation_types (id, name) VALUES (:id, :name) "
            "ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name"
        ),
        _RELATION_ROWS,
    )

    # ── เพิ่ม column FK + ลบ column เดิม ───────────────────────────────────────
    op.add_column(
        "household_members",
        sa.Column(
            "relation_to_applicant_id",
            sa.Integer(),
            nullable=True,
            comment="FK → household_member_relation_types",
        ),
    )
    op.create_foreign_key(
        op.f("fk_household_members_relation_to_applicant_id_household_member_relation_types"),
        "household_members",
        "household_member_relation_types",
        ["relation_to_applicant_id"],
        ["id"],
    )
    op.drop_column("household_members", "relation_to_applicant")

    # ── เพิ่ม prefix เด็กหญิง / เด็กชาย ────────────────────────────────────────
    conn.execute(
        sa.text(
            "INSERT INTO prefix_type (id, name) VALUES (:id, :name) "
            "ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name"
        ),
        _PREFIX_EXTRA,
    )


def downgrade() -> None:
    conn = op.get_bind()

    # ลบ prefix เด็กหญิง/เด็กชาย ออก (ลบเฉพาะถ้าไม่มี FK จากที่อื่น)
    conn.execute(sa.text("DELETE FROM prefix_type WHERE id IN (4, 5)"))

    # คืน column relation_to_applicant
    op.add_column(
        "household_members",
        sa.Column(
            "relation_to_applicant",
            sa.String(length=100),
            nullable=True,
            comment="ความสัมพันธ์กับผู้ประสบปัญหา",
        ),
    )

    # ลบ FK + column ใหม่
    op.drop_constraint(
        op.f("fk_household_members_relation_to_applicant_id_household_member_relation_types"),
        "household_members",
        type_="foreignkey",
    )
    op.drop_column("household_members", "relation_to_applicant_id")

    # ลบตาราง relation types
    op.drop_table("household_member_relation_types")
