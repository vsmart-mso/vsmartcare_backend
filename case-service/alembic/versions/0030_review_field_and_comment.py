"""review_field master data + welfare_review_comment junction

Revision ID: 0030_review_field_and_comment
Revises: 0029_current_status_id_10
Create Date: 2026-05-18 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_review_field_and_comment"
down_revision: str | Sequence[str] | None = "0029_current_status_id_10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_REVIEW_FIELD_ROWS: list[dict] = [
    # ── Step 1: ที่อยู่และข้อมูลติดต่อ ──────────────────────────────────────
    {"id": 1,  "name": "current_address_house_no",          "label": "บ้านเลขที่",                                       "step": 1, "display_order": 1,  "is_active": True},
    {"id": 2,  "name": "current_address_moo",               "label": "หมู่ที่",                                          "step": 1, "display_order": 2,  "is_active": True},
    {"id": 3,  "name": "current_address_village",           "label": "ชื่อหมู่บ้าน",                                    "step": 1, "display_order": 3,  "is_active": True},
    {"id": 4,  "name": "current_address_alley",             "label": "ตรอก",                                             "step": 1, "display_order": 4,  "is_active": True},
    {"id": 5,  "name": "current_address_soi",               "label": "ซอย",                                              "step": 1, "display_order": 5,  "is_active": True},
    {"id": 6,  "name": "current_address_road",              "label": "ถนน",                                              "step": 1, "display_order": 6,  "is_active": True},
    {"id": 7,  "name": "current_address_province",          "label": "จังหวัด",                                          "step": 1, "display_order": 7,  "is_active": True},
    {"id": 8,  "name": "current_address_district",          "label": "อำเภอ/เขต",                                       "step": 1, "display_order": 8,  "is_active": True},
    {"id": 9,  "name": "current_address_subdistrict",       "label": "ตำบล/แขวง",                                       "step": 1, "display_order": 9,  "is_active": True},
    {"id": 10, "name": "current_address_gps",               "label": "ตำแหน่ง GPS",                                     "step": 1, "display_order": 10, "is_active": True},
    {"id": 11, "name": "contact_phone_home",                "label": "โทรศัพท์ (บ้าน/ที่ทำงาน)",                        "step": 1, "display_order": 11, "is_active": True},
    {"id": 12, "name": "contact_fax",                       "label": "โทรสาร",                                           "step": 1, "display_order": 12, "is_active": True},
    {"id": 13, "name": "contact_mobile",                    "label": "โทรศัพท์มือถือ",                                  "step": 1, "display_order": 13, "is_active": True},
    {"id": 14, "name": "contact_email",                     "label": "อีเมล",                                            "step": 1, "display_order": 14, "is_active": True},
    {"id": 15, "name": "marital_status",                    "label": "สถานภาพสมรส",                                     "step": 1, "display_order": 15, "is_active": True},
    {"id": 16, "name": "housing_type",                      "label": "ลักษณะที่อยู่อาศัย",                              "step": 1, "display_order": 16, "is_active": True},
    {"id": 17, "name": "housing_rent",                      "label": "ค่าเช่าต่อเดือน (บาท)",                           "step": 1, "display_order": 17, "is_active": True},
    {"id": 18, "name": "family_members_count",              "label": "จำนวนสมาชิกในครอบครัว (คน)",                      "step": 1, "display_order": 18, "is_active": True},
    # ── Step 2: เศรษฐกิจครอบครัว ────────────────────────────────────────────
    {"id": 19, "name": "family_occupation",                 "label": "อาชีพหลักของครอบครัว",                            "step": 2, "display_order": 1,  "is_active": True},
    {"id": 20, "name": "family_income",                     "label": "รายได้เฉลี่ยต่อเดือนของครอบครัว (บาท)",          "step": 2, "display_order": 2,  "is_active": True},
    {"id": 21, "name": "income_sources",                    "label": "ที่มาของรายได้",                                  "step": 2, "display_order": 3,  "is_active": True},
    {"id": 22, "name": "income_source_other",               "label": "ที่มาของรายได้ อื่น ๆ (ระบุ)",                   "step": 2, "display_order": 4,  "is_active": True},
    {"id": 23, "name": "dependents",                        "label": "ภาระการอุปการะ",                                  "step": 2, "display_order": 5,  "is_active": True},
    {"id": 24, "name": "dependents_other",                  "label": "ภาระการอุปการะ อื่น ๆ (ระบุ)",                   "step": 2, "display_order": 6,  "is_active": True},
    {"id": 25, "name": "gov_aid_received",                  "label": "ประวัติการได้รับความช่วยเหลือจากรัฐ",             "step": 2, "display_order": 7,  "is_active": True},
    {"id": 26, "name": "gov_aid_count",                     "label": "จำนวนครั้งที่ได้รับความช่วยเหลือในปีงบประมาณนี้","step": 2, "display_order": 8,  "is_active": True},
    {"id": 27, "name": "gov_aid_amount",                    "label": "มูลค่าความช่วยเหลือ รวมเป็นเงิน (บาท)",           "step": 2, "display_order": 9,  "is_active": True},
    {"id": 28, "name": "gov_aid_types",                     "label": "ประเภทความช่วยเหลือที่เคยได้รับ",                 "step": 2, "display_order": 10, "is_active": True},
    {"id": 29, "name": "gov_aid_type_detail",               "label": "รายละเอียดความช่วยเหลือที่เคยได้รับ (ระบุ)",     "step": 2, "display_order": 11, "is_active": True},
    # ── Step 3: ปัญหาและความช่วยเหลือที่ต้องการ ──────────────────────────────
    {"id": 30, "name": "family_problems",                   "label": "สภาพปัญหาความเดือดร้อนของครอบครัว",              "step": 3, "display_order": 1,  "is_active": True},
    {"id": 31, "name": "requested_assistance_type",         "label": "ประเภทความช่วยเหลือที่ต้องการ",                  "step": 3, "display_order": 2,  "is_active": True},
    {"id": 32, "name": "bank_name",                         "label": "ธนาคาร",                                          "step": 3, "display_order": 3,  "is_active": True},
    {"id": 33, "name": "bank_account_number",               "label": "เลขที่บัญชีธนาคาร",                              "step": 3, "display_order": 4,  "is_active": True},
    {"id": 34, "name": "bank_book_photo",                   "label": "รูปหน้าสมุดบัญชีธนาคาร",                         "step": 3, "display_order": 5,  "is_active": True},
    # ── Step 4: เอกสารและหลักฐาน ────────────────────────────────────────────
    {"id": 35, "name": "evidence_house_exterior",           "label": "รูปสภาพบ้านภายนอก",                              "step": 4, "display_order": 1,  "is_active": True},
    {"id": 36, "name": "evidence_house_interior",           "label": "รูปสภาพบ้านภายใน",                               "step": 4, "display_order": 2,  "is_active": True},
    {"id": 37, "name": "evidence_person_photo",             "label": "รูปผู้ประสบปัญหาฯ",                              "step": 4, "display_order": 3,  "is_active": True},
    {"id": 38, "name": "evidence_problem_photo",            "label": "รูปสภาพปัญหาที่ต้องการให้ความช่วยเหลือ",         "step": 4, "display_order": 4,  "is_active": True},
    {"id": 39, "name": "evidence_family_photo",             "label": "รูปสมาชิกในครอบครัว",                            "step": 4, "display_order": 5,  "is_active": True},
    {"id": 40, "name": "doc_house_registration_house",      "label": "รูปทะเบียนบ้าน (รายการเกี่ยวกับบ้าน)",          "step": 4, "display_order": 6,  "is_active": True},
    {"id": 41, "name": "doc_house_registration_person",     "label": "รูปทะเบียนบ้าน (รายการเกี่ยวกับบุคคล)",        "step": 4, "display_order": 7,  "is_active": True},
    {"id": 42, "name": "doc_other",                         "label": "รูปอื่น ๆ (เอกสารแนบเพิ่มเติม)",               "step": 4, "display_order": 8,  "is_active": True},
]


def _upsert_by_id(table: str, rows: list[dict]) -> None:
    if not rows:
        return
    cols = list(rows[0].keys())
    col_list = ", ".join(cols)
    value_placeholders = ", ".join([f":{c}" for c in cols])
    set_cols = [c for c in cols if c != "id"]
    set_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in set_cols])
    sql = (
        f"INSERT INTO {table} ({col_list}) VALUES ({value_placeholders}) "
        f"ON CONFLICT (id) DO UPDATE SET {set_clause}"
    )
    op.get_bind().execute(sa.text(sql), rows)


def upgrade() -> None:
    op.create_table(
        "review_field",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_review_field")),
        sa.UniqueConstraint("name", name=op.f("uq_review_field_name")),
    )

    op.create_table(
        "welfare_review_comment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("welfare_request_status_id", sa.Integer(), nullable=False),
        sa.Column("review_field_id", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["welfare_request_status_id"],
            ["welfare_request_status.id"],
            name=op.f("fk_welfare_review_comment_welfare_request_status_id_welfare_request_status"),
        ),
        sa.ForeignKeyConstraint(
            ["review_field_id"],
            ["review_field.id"],
            name=op.f("fk_welfare_review_comment_review_field_id_review_field"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_welfare_review_comment")),
        sa.UniqueConstraint(
            "welfare_request_status_id",
            "review_field_id",
            name="uq_welfare_review_comment_status_field",
        ),
    )
    op.create_index(
        op.f("ix_welfare_review_comment_welfare_request_status_id"),
        "welfare_review_comment",
        ["welfare_request_status_id"],
        unique=False,
    )

    _upsert_by_id("review_field", _REVIEW_FIELD_ROWS)
    op.execute(
        sa.text(
            "SELECT setval(pg_get_serial_sequence('review_field', 'id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM review_field))"
        )
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_welfare_review_comment_welfare_request_status_id"),
        table_name="welfare_review_comment",
    )
    op.drop_table("welfare_review_comment")
    op.drop_table("review_field")
