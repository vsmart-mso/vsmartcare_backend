"""สร้าง occupation_types master table และเพิ่ม FK columns ใน economic_infos / household_members

Revision ID: 0065_occupation_types
Revises: 0064_hardship_status_types
Create Date: 2026-06-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0065_occupation_types"
down_revision = "0064_hardship_status_types"
branch_labels = None
depends_on = None

_OCCUPATION_ROWS = [
    {"id": 1,  "name": "นักเรียน/นักศึกษา"},
    {"id": 2,  "name": "ค้าขาย/ธุรกิจส่วนตัว"},
    {"id": 3,  "name": "ภิกษุ/สามเณร/แม่ชี"},
    {"id": 4,  "name": "เกษตรกร (ทำไร่/นา/สวน/เลี้ยงสัตว์/ประมง)"},
    {"id": 5,  "name": "รับจ้าง"},
    {"id": 6,  "name": "ข้าราชการ/พนักงานของรัฐ"},
    {"id": 7,  "name": "พนักงานรัฐวิสาหกิจ"},
    {"id": 8,  "name": "พนักงานบริษัท"},
    {"id": 99, "name": "อื่น ๆ ระบุ (เพิ่มระบุอื่นๆ)"},
]


def upgrade() -> None:
    # 1. สร้าง occupation_types table
    op.create_table(
        "occupation_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_occupation_types")),
    )

    # 2. Seed ข้อมูล
    op.bulk_insert(
        sa.table(
            "occupation_types",
            sa.column("id", sa.Integer),
            sa.column("name", sa.String),
        ),
        _OCCUPATION_ROWS,
    )

    # 3. เพิ่ม occupation_type_id FK ใน household_members
    op.add_column(
        "household_members",
        sa.Column("occupation_type_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_household_members_occupation_type_id_occupation_types"),
        "household_members",
        "occupation_types",
        ["occupation_type_id"],
        ["id"],
    )

    # 4. เพิ่ม occupation_type_id FK ใน economic_infos (อาชีพผู้ยื่นคำร้อง)
    op.add_column(
        "economic_infos",
        sa.Column("occupation_type_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_economic_infos_occupation_type_id_occupation_types"),
        "economic_infos",
        "occupation_types",
        ["occupation_type_id"],
        ["id"],
    )

    # 5. เพิ่ม family_occupation_type_id FK ใน economic_infos (อาชีพหลักของครอบครัว)
    op.add_column(
        "economic_infos",
        sa.Column("family_occupation_type_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_economic_infos_family_occupation_type_id_occupation_types"),
        "economic_infos",
        "occupation_types",
        ["family_occupation_type_id"],
        ["id"],
    )

    # 6. Migrate ข้อมูลเก่า — ทุก record ที่มี occupation/family_occupation อยู่แล้ว
    #    ให้ถือว่าเป็น "อื่น ๆ ระบุ" (id=99) เพราะข้อความเก่าจะยังคงอยู่ในคอลัมน์ text
    op.execute(
        """
        UPDATE household_members
        SET occupation_type_id = 99
        WHERE occupation IS NOT NULL AND occupation != ''
        """
    )
    op.execute(
        """
        UPDATE economic_infos
        SET occupation_type_id = 99
        WHERE occupation IS NOT NULL AND occupation != ''
        """
    )
    op.execute(
        """
        UPDATE economic_infos
        SET family_occupation_type_id = 99
        WHERE family_occupation IS NOT NULL AND family_occupation != ''
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_economic_infos_family_occupation_type_id_occupation_types"),
        "economic_infos",
        type_="foreignkey",
    )
    op.drop_column("economic_infos", "family_occupation_type_id")

    op.drop_constraint(
        op.f("fk_economic_infos_occupation_type_id_occupation_types"),
        "economic_infos",
        type_="foreignkey",
    )
    op.drop_column("economic_infos", "occupation_type_id")

    op.drop_constraint(
        op.f("fk_household_members_occupation_type_id_occupation_types"),
        "household_members",
        type_="foreignkey",
    )
    op.drop_column("household_members", "occupation_type_id")

    op.drop_table("occupation_types")
