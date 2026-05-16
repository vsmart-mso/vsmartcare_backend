"""merge 0019 heads

Revision ID: 0020_merge_0019_heads
Revises: 0019_attachment_pdf_037_038, 0019_update_current_status_dropdown
Create Date: 2026-05-16 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0020_merge_0019_heads"
down_revision: str | Sequence[str] | None = (
    "0019_attachment_pdf_037_038",
    "0019_update_status_dropdown",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
