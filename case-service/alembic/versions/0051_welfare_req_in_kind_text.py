"""เพิ่ม request_in_kind_text ใน welfare_request_types สำหรับประเภท 'ช่วยเหลือเป็นสิ่งของ' (id=2)

Revision ID: 0051_welfare_req_in_kind_text
Revises: 0050_household_members_table
Create Date: 2026-06-10 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0051_welfare_req_in_kind_text"
down_revision: str | Sequence[str] | None = "0050_household_members_table"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "welfare_request_types",
        sa.Column(
            "request_in_kind_text",
            sa.String(500),
            nullable=True,
            comment="ระบุรายละเอียดเมื่อเลือก 'ช่วยเหลือเป็นสิ่งของ' (request_type_id=2)",
        ),
    )


def downgrade() -> None:
    op.drop_column("welfare_request_types", "request_in_kind_text")
