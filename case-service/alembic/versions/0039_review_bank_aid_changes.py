"""ปิด field bank_name / bank_account_number / requested_assistance_type, ย้าย bank_book_photo
ไป step 4 และเพิ่ม requested_assistance_detail (textarea รายละเอียดการช่วยเหลือ).

Revision ID: 0039_review_bank_aid_changes
Revises: 0038_welfare_req_other_text
Create Date: 2026-05-20 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039_review_bank_aid_changes"
down_revision: str | Sequence[str] | None = "0038_welfare_req_other_text"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# id ของ row เดิมใน review_field (อ้างอิงจาก migration 0030)
_ID_REQUESTED_ASSISTANCE_TYPE = 31
_ID_BANK_NAME = 32
_ID_BANK_ACCOUNT_NUMBER = 33
_ID_BANK_BOOK_PHOTO = 34


def upgrade() -> None:
    conn = op.get_bind()

    # 1) ปิดการใช้งาน 3 field เดิม (UI ไม่แสดงแล้ว — เจ้าหน้าที่ส่งกลับแก้ไม่ได้)
    conn.execute(
        sa.text(
            "UPDATE review_field SET is_active = false "
            "WHERE id IN (:f1, :f2, :f3)"
        ),
        {
            "f1": _ID_REQUESTED_ASSISTANCE_TYPE,
            "f2": _ID_BANK_NAME,
            "f3": _ID_BANK_ACCOUNT_NUMBER,
        },
    )

    # 2) ย้าย bank_book_photo: step 3 → step 4 (display_order ต่อท้าย doc_other = 9)
    #    label ปรับให้สอดคล้องตำแหน่งใหม่ (อยู่ใต้เอกสารแนบเพิ่มเติม)
    conn.execute(
        sa.text(
            "UPDATE review_field "
            "SET step = 4, display_order = 9 "
            "WHERE id = :fid"
        ),
        {"fid": _ID_BANK_BOOK_PHOTO},
    )

    # 3) เพิ่ม field ใหม่: requested_assistance_detail (textarea 10.1)
    #    ใช้ ON CONFLICT (name) DO UPDATE เผื่อรันซ้ำ
    conn.execute(
        sa.text(
            "INSERT INTO review_field (name, label, step, display_order, is_active) "
            "VALUES (:name, :label, :step, :display_order, :is_active) "
            "ON CONFLICT (name) DO UPDATE SET "
            "  label = EXCLUDED.label, "
            "  step = EXCLUDED.step, "
            "  display_order = EXCLUDED.display_order, "
            "  is_active = EXCLUDED.is_active"
        ),
        {
            "name": "requested_assistance_detail",
            "label": "รายละเอียดการช่วยเหลือที่ต้องการ",
            "step": 3,
            "display_order": 2,
            "is_active": True,
        },
    )


def downgrade() -> None:
    conn = op.get_bind()

    # 1) ลบ row ที่ insert ใหม่
    conn.execute(
        sa.text("DELETE FROM review_field WHERE name = :name"),
        {"name": "requested_assistance_detail"},
    )

    # 2) ย้าย bank_book_photo กลับ step 3 display_order 5
    conn.execute(
        sa.text(
            "UPDATE review_field "
            "SET step = 3, display_order = 5 "
            "WHERE id = :fid"
        ),
        {"fid": _ID_BANK_BOOK_PHOTO},
    )

    # 3) เปิดใช้งาน 3 field เดิมกลับ
    conn.execute(
        sa.text(
            "UPDATE review_field SET is_active = true "
            "WHERE id IN (:f1, :f2, :f3)"
        ),
        {
            "f1": _ID_REQUESTED_ASSISTANCE_TYPE,
            "f2": _ID_BANK_NAME,
            "f3": _ID_BANK_ACCOUNT_NUMBER,
        },
    )
