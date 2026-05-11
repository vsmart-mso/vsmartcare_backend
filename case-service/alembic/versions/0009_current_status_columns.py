"""current_status: ลบ name, เปลี่ยน description -> description_staff, เพิ่มคอลัมน์ UI/กรอง + seed 5 แถว

- แมป FK welfare_request_status: เดิม 1–4 -> 2–5 (เดิม id=4 ไม่ตรงเกณฑ์ -> id=5)
- เพิ่มแถว id=5

Revision ID: 0009_current_status_cols
Revises: 0008_app_req_rel_scr
Create Date: 2026-05-10 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_current_status_cols"
down_revision: str | Sequence[str] | None = "0008_app_req_rel_scr"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("current_status", sa.Column("description_public", sa.Text(), nullable=True))
    op.add_column("current_status", sa.Column("color", sa.String(length=32), nullable=True))
    op.add_column("current_status", sa.Column("dropdown_to_change", sa.String(length=255), nullable=True))
    op.add_column("current_status", sa.Column("dropdown_order", sa.Integer(), nullable=True))
    op.add_column(
        "current_status",
        sa.Column("dropdown_activate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("current_status", sa.Column("filter_order", sa.Integer(), nullable=True))
    op.add_column(
        "current_status",
        sa.Column("filter_activate", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.alter_column(
        "current_status",
        "name",
        existing_type=sa.String(length=255),
        nullable=True,
    )

    op.execute(sa.text("ALTER TABLE current_status RENAME COLUMN description TO description_staff"))

    op.execute(
        sa.text(
            """
            INSERT INTO current_status (
                id, name, description_staff, description_public, color, dropdown_to_change,
                dropdown_order, dropdown_activate, filter_order, filter_activate
            ) VALUES (
                5, NULL,
                'คุณสมบัติไม่ตรงตามหลักเกณฑ์',
                'คุณสมบัติไม่ตรงตามหลักเกณฑ์',
                '#ff0000',
                'ช่วยเหลือแล้ว*',
                5, TRUE, 5, TRUE
            )
            ON CONFLICT (id) DO NOTHING
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE welfare_request_status
            SET current_status_id = CASE current_status_id
                WHEN 4 THEN 5
                WHEN 3 THEN 4
                WHEN 2 THEN 3
                WHEN 1 THEN 2
                ELSE current_status_id
            END
            WHERE current_status_id IN (1, 2, 3, 4)
            """
        )
    )

    op.execute(
        sa.text(
            """
            UPDATE current_status SET
                name = NULL,
                description_public = CASE id
                    WHEN 1 THEN 'รอรับเรื่อง'
                    WHEN 2 THEN 'รับเรื่องเรียบร้อย'
                    WHEN 3 THEN 'อยู่ระหว่างการเบิก'
                    WHEN 4 THEN 'เบิกจ่ายสำเร็จ'
                    WHEN 5 THEN 'คุณสมบัติไม่ตรงตามหลักเกณฑ์'
                END,
                description_staff = CASE id
                    WHEN 1 THEN 'รอรับเรื่อง'
                    WHEN 2 THEN 'รับเรื่องเรียบร้อย'
                    WHEN 3 THEN 'อยู่ระหว่างการเบิก'
                    WHEN 4 THEN 'ช่วยเหลือแล้ว'
                    WHEN 5 THEN 'คุณสมบัติไม่ตรงตามหลักเกณฑ์'
                END,
                color = CASE id
                    WHEN 1 THEN '#009f75'
                    WHEN 2 THEN '#ca9d15'
                    WHEN 3 THEN '#0084ff'
                    WHEN 4 THEN '#009f75'
                    WHEN 5 THEN '#ff0000'
                END,
                dropdown_to_change = CASE id
                    WHEN 1 THEN 'none'
                    WHEN 2 THEN 'รับเรื่อง*'
                    WHEN 3 THEN 'อยู่ระหว่างการเบิก*'
                    WHEN 4 THEN 'ช่วยเหลือแล้ว*'
                    WHEN 5 THEN 'ช่วยเหลือแล้ว*'
                END,
                dropdown_order = CASE id
                    WHEN 1 THEN 1 WHEN 2 THEN 2 WHEN 3 THEN 3 WHEN 4 THEN 4 WHEN 5 THEN 5
                END,
                dropdown_activate = CASE id
                    WHEN 1 THEN FALSE ELSE TRUE
                END,
                filter_order = CASE id
                    WHEN 1 THEN 1 WHEN 2 THEN 2 WHEN 3 THEN 3 WHEN 4 THEN 4 WHEN 5 THEN 5
                END,
                filter_activate = TRUE
            WHERE id IN (1, 2, 3, 4, 5)
            """
        )
    )

    op.drop_column("current_status", "name")

    op.alter_column(
        "current_status",
        "description_public",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.alter_column(
        "current_status",
        "description_staff",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.alter_column(
        "current_status",
        "color",
        existing_type=sa.String(length=32),
        nullable=False,
    )
    op.alter_column(
        "current_status",
        "dropdown_to_change",
        existing_type=sa.String(length=255),
        nullable=False,
    )
    op.alter_column(
        "current_status",
        "dropdown_order",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.alter_column(
        "current_status",
        "filter_order",
        existing_type=sa.Integer(),
        nullable=False,
    )

    op.alter_column(
        "current_status",
        "dropdown_activate",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=None,
    )
    op.alter_column(
        "current_status",
        "filter_activate",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=None,
    )

    op.execute(
        sa.text(
            "SELECT setval(pg_get_serial_sequence('current_status', 'id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM current_status))"
        )
    )


def downgrade() -> None:
    raise NotImplementedError(
        "downgrade 0009_current_status_cols: ย้อนโครงสร้าง current_status และ FK ไม่ปลอดภัยอัตโนมัติ"
    )
