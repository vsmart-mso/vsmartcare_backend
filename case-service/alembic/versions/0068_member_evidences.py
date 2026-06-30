"""เพิ่ม household_member_id ใน welfare_evidences + attachment_types สำหรับเอกสารสมาชิก

เหตุผล:
  - รองรับอัปโหลดรูปภาพเอกสารของสมาชิกในครัวเรือนแต่ละคน (บัตรประชาชน, ทะเบียนบ้าน, อื่นๆ)
  - ใช้ตาราง welfare_evidences เดิม — เพิ่มแค่ FK nullable ไปยัง household_members
  - เมื่อ household_member_id IS NULL → evidence ของผู้ยื่นคำร้อง (เดิม)
  - เมื่อ household_member_id IS NOT NULL → evidence ของสมาชิกในครัวเรือนคนนั้น
  - CASCADE DELETE: ลบสมาชิก → รูปหายตามอัตโนมัติ ไม่ต้องจัดการ manual
  - Index (household_member_id) ป้องกัน slow query เมื่อ filter by member
  - Index composite (applicant_id, household_member_id) ใช้ query รูปทั้งหมดของสมาชิกใน applicant

Attachment types ใหม่ (seed):
  id=12  member_id_card       — บัตรประชาชนสมาชิก
  id=13  member_house_home    — ทะเบียนบ้าน รายการเกี่ยวกับบ้าน
  id=14  member_house_person  — ทะเบียนบ้าน รายการเกี่ยวกับบุคคล
  id=15  member_other         — เอกสารอื่นๆ ของสมาชิก

Revision ID: 0067_member_evidences
Revises: 0066_cover_document_batch
Create Date: 2026-06-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0068_member_evidences"
down_revision = "0067_article_approver_sdhsv_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. เพิ่ม household_member_id (nullable FK) ลงใน welfare_evidences
    #    - nullable=True เพราะ evidence เดิมทั้งหมดไม่มีข้อมูลสมาชิก
    #    - ondelete="CASCADE" → ลบ household_member → รูปหายตาม
    op.add_column(
        "welfare_evidences",
        sa.Column(
            "household_member_id",
            sa.Integer(),
            nullable=True,
            comment="FK → household_members.id (NULL = evidence ของผู้ยื่น, NOT NULL = evidence ของสมาชิก)",
        ),
    )

    # 2. สร้าง FK constraint
    op.create_foreign_key(
        op.f("fk_welfare_evidences_household_member_id_household_members"),
        "welfare_evidences",
        "household_members",
        ["household_member_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # 3. Index บน household_member_id — ใช้ query รูปของสมาชิกคนเดียว
    op.create_index(
        op.f("ix_welfare_evidences_household_member_id"),
        "welfare_evidences",
        ["household_member_id"],
        unique=False,
    )

    # 4. Index composite (applicant_id, household_member_id) — ใช้ query รูปสมาชิกทั้งหมดใน case
    #    เหตุผล: ตอน load case ใน edit mode ต้องดึงรูปทุกสมาชิกพร้อมกัน โดย filter applicant_id
    op.create_index(
        "ix_welfare_evidences_applicant_member",
        "welfare_evidences",
        ["applicant_id", "household_member_id"],
        unique=False,
    )

    # 5. Seed attachment_types: เพิ่มเฉพาะ id=12 'id_card' (บัตรประชาชน)
    #    - house_home (6), house_person (7), other (99) ใช้ร่วมกับผู้ยื่นได้ผ่าน household_member_id
    #    - ตั้งชื่อ 'id_card' ไม่ใส่ prefix 'member_' เผื่ออนาคตผู้ยื่นอาจใช้ type นี้ด้วย
    op.execute("""
        INSERT INTO attachment_types (id, name)
        VALUES (12, 'id_card')
        ON CONFLICT (id) DO NOTHING
    """)


def downgrade() -> None:
    # ลบ attachment_types ที่เพิ่มมา
    op.execute("DELETE FROM attachment_types WHERE id = 12")

    # ลบ index + FK + column ตามลำดับกลับ
    op.drop_index("ix_welfare_evidences_applicant_member", table_name="welfare_evidences")
    op.drop_index(op.f("ix_welfare_evidences_household_member_id"), table_name="welfare_evidences")
    op.drop_constraint(
        op.f("fk_welfare_evidences_household_member_id_household_members"),
        "welfare_evidences",
        type_="foreignkey",
    )
    op.drop_column("welfare_evidences", "household_member_id")
