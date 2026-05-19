"""เพิ่ม request_other_text ใน welfare_request_types สำหรับประเภท 'ช่วยเหลือเรื่องอื่นๆ'.

Revision ID: 0038_welfare_req_other_text
Revises: 0037_status_10_desc_public
Create Date: 2026-05-19 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038_welfare_req_other_text"
down_revision: str | Sequence[str] | None = "0037_status_10_desc_public"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "welfare_request_types",
        sa.Column("request_other_text", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("welfare_request_types", "request_other_text")
