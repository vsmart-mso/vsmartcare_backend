"""case_diagnosis + case_diagnosis_edit_history (BR-DIAG-01..06)

คำวินิจฉัยหลายรายการต่อเคส ผูกกับ user ผู้บันทึก + ประวัติการแก้ไข
พร้อม data migration: ย้าย comment เดิมจาก case_regulation_choice มาเป็น
คำวินิจฉัยแถวแรก (owner_user_id=0 = ไม่ทราบเจ้าของ, read-only ถาวร)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0070_case_diagnosis"
down_revision = "0069_merge_0068_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_diagnosis",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("diagnosis_text", sa.Text(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("owner_sdshv", sa.String(length=255), nullable=True),
        sa.Column("owner_name", sa.String(length=255), nullable=True),
        sa.Column("owner_position", sa.String(length=255), nullable=True),
        sa.Column("owner_organization", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_case_diagnosis_applicant_id_applicants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_diagnosis")),
        sa.UniqueConstraint(
            "applicant_id", "owner_user_id", name="uq_case_diagnosis_applicant_owner"
        ),
    )
    op.create_index(
        op.f("ix_case_diagnosis_applicant_id"), "case_diagnosis", ["applicant_id"], unique=False
    )
    op.create_index(
        op.f("ix_case_diagnosis_owner_user_id"), "case_diagnosis", ["owner_user_id"], unique=False
    )

    op.create_table(
        "case_diagnosis_edit_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("diagnosis_id", sa.Integer(), nullable=False),
        sa.Column("old_text", sa.Text(), nullable=False),
        sa.Column("new_text", sa.Text(), nullable=False),
        sa.Column("edit_reason", sa.Text(), nullable=True),
        sa.Column("edited_by_user_id", sa.Integer(), nullable=False),
        sa.Column("edited_by_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["diagnosis_id"],
            ["case_diagnosis.id"],
            name=op.f("fk_case_diagnosis_edit_history_diagnosis_id_case_diagnosis"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_diagnosis_edit_history")),
    )
    op.create_index(
        op.f("ix_case_diagnosis_edit_history_diagnosis_id"),
        "case_diagnosis_edit_history",
        ["diagnosis_id"],
        unique=False,
    )

    # data migration: comment เดิม (1:1) → case_diagnosis แถวแรกของเคส
    # owner_user_id=0 = migrate มาจากระบบเดิม ไม่ทราบ user id — แสดงได้ แก้ไม่ได้
    op.execute(
        sa.text(
            """
            INSERT INTO case_diagnosis
                (applicant_id, diagnosis_text, owner_user_id, owner_sdshv,
                 created_at, updated_at)
            SELECT ch.applicant_id,
                   crc.comment,
                   0,
                   COALESCE(NULLIF(crc.signed_by_sdshv, ''), NULLIF(ch.sw_user_sdshv, '')),
                   crc.created_at,
                   crc.updated_at
            FROM case_regulation_choice crc
            JOIN case_handling ch ON ch.id = crc.case_handling_id
            WHERE crc.comment IS NOT NULL
              AND btrim(crc.comment) <> ''
            """
        )
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_case_diagnosis_edit_history_diagnosis_id"),
        table_name="case_diagnosis_edit_history",
    )
    op.drop_table("case_diagnosis_edit_history")
    op.drop_index(op.f("ix_case_diagnosis_owner_user_id"), table_name="case_diagnosis")
    op.drop_index(op.f("ix_case_diagnosis_applicant_id"), table_name="case_diagnosis")
    op.drop_table("case_diagnosis")
