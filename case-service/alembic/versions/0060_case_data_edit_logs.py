"""merge 0059_admin_province_access + 0058_case_data_edit_logs → head เดียว

Revision ID: 0060_case_data_edit_logs
Revises: 0059_admin_province_access, 0058_case_data_edit_logs
Create Date: 2026-06-12

DDL อยู่ที่ 0058_case_data_edit_logs — revision นี้เป็น merge point เท่านั้น
(DB ที่ stamp 0058_case_data_edit_logs อยู่แล้วจะ upgrade ผ่าน 0058_approve → 0059 แล้ว merge ที่นี่)
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0060_case_data_edit_logs"
down_revision: str | Sequence[str] | None = (
    "0059_admin_province_access",
    "0058_case_data_edit_logs",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
