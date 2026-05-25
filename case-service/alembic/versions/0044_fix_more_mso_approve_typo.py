"""fix more_mso approve column name typos (appove → approve)

Revision ID: 0044_fix_more_mso_approve_typo
Revises: 0043_mso_type_send
Create Date: 2026-05-25 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0044_fix_more_mso_approve_typo"
down_revision: str | Sequence[str] | None = "0043_mso_type_send"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("more_mso", "appove_name", new_column_name="approve_name")
    op.alter_column("more_mso", "appove_number", new_column_name="approve_number")
    op.alter_column("more_mso", "appove_date", new_column_name="approve_date")


def downgrade() -> None:
    op.alter_column("more_mso", "approve_name", new_column_name="appove_name")
    op.alter_column("more_mso", "approve_number", new_column_name="appove_number")
    op.alter_column("more_mso", "approve_date", new_column_name="appove_date")
