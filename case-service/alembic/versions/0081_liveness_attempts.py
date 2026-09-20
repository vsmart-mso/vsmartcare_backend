"""สร้างตาราง liveness_attempts — ด่านยืนยันตัวตนด้วยใบหน้า ก่อนยื่นคำร้อง (AINU eKYC)

Revision ID: 0081_liveness_attempts
Revises: 0080_send_data_audit_log
Create Date: 2026-09-07

case-service เป็นเจ้าของทั้ง migration และ endpoint — ไม่มี service แยก

⚠️ ตั้งใจไม่ใส่ guard `if inspect(bind).has_table(...): return`
DB dev บางเครื่องมีตารางนี้ค้างอยู่จาก branch `liveness-service` (schema เก่า คนละหน้าตา)
แต่ `alembic_version` ยังเป็น 0080 → guard จะข้ามการสร้างแล้ว stamp เป็น 0081
ทำให้ได้ schema เก่าโดยไม่มีใครรู้ แล้วไปพังตอน runtime แทน
ปล่อยให้ `relation already exists` ดังตั้งแต่ตอน migrate ดีกว่า — วิธีแก้คือ DROP ตารางเก่าก่อน
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0081_liveness_attempts"
down_revision: str | Sequence[str] | None = "0080_send_data_audit_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "liveness_attempts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        # เจ้าของการสแกน — รู้ตั้งแต่เปิด session ส่วน applicant ยังไม่เกิด
        sa.Column("persons_id", sa.Integer(), nullable=False),
        sa.Column("reference_id", sa.String(length=64), nullable=False),
        sa.Column("transaction_id", sa.String(length=128), nullable=True),
        # pending / completed / failed / skipped
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("liveness_reason", sa.String(length=64), nullable=True),
        sa.Column("fail_reason", sa.String(length=64), nullable=True),
        sa.Column("skip_reason", sa.String(length=64), nullable=True),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("sdk_version", sa.String(length=64), nullable=True),
        sa.Column("device", sa.String(length=255), nullable=True),
        # JSON ไม่ใช่ JSONB — JSONB เรียง key ใหม่ ทำให้เสียความเป็น "ดิบตามที่ได้รับ"
        # และฟิลด์ที่ต้อง query ถูกดึงออกมาเป็นคอลัมน์แล้ว
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("applicant_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["persons_id"],
            ["persons.id"],
            name=op.f("fk_liveness_attempts_persons_id_persons"),
            ondelete="CASCADE",
        ),
        # SET NULL ตาม pattern ocr_results — ลบคำร้องแล้วสถิติการสแกนต้องไม่หายไปด้วย
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_liveness_attempts_applicant_id_applicants"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_liveness_attempts")),
    )
    # ห้าม unique บน persons_id/applicant_id — ผู้ใช้สแกนซ้ำได้ไม่จำกัด แต่ละครั้งเป็น transaction ใหม่
    op.create_index(
        op.f("ix_liveness_attempts_persons_id"),
        "liveness_attempts",
        ["persons_id"],
    )
    op.create_index(
        op.f("ix_liveness_attempts_reference_id"),
        "liveness_attempts",
        ["reference_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_liveness_attempts_applicant_id"),
        "liveness_attempts",
        ["applicant_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_liveness_attempts_applicant_id"), table_name="liveness_attempts")
    op.drop_index(op.f("ix_liveness_attempts_reference_id"), table_name="liveness_attempts")
    op.drop_index(op.f("ix_liveness_attempts_persons_id"), table_name="liveness_attempts")
    op.drop_table("liveness_attempts")
