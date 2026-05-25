"""merge 0044 migration heads

Revision ID: 0045_merge_0044_heads
Revises: 0044_allow_multiple_037_rounds, 0044_fix_more_mso_approve_typo
Create Date: 2026-05-25 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0045_merge_0044_heads"
down_revision: str | Sequence[str] | None = (
    "0044_allow_multiple_037_rounds",
    "0044_fix_more_mso_approve_typo",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
