"""merge 0068 heads

Revision ID: 0069_merge_0068_heads
Revises: 0068_member_evidences, 0068_staff_users_audit
Create Date: 2026-07-02 15:08:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0069_merge_0068_heads"
down_revision: str | Sequence[str] | None = (
    "0068_member_evidences",
    "0068_staff_users_audit",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
