"""Add requested approver to article.

Revision ID: 0067_article_approver_sdhsv_id
Revises: 0066_cover_document_batch
Create Date: 2026-06-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0067_article_approver_sdhsv_id"
down_revision = "0066_cover_document_batch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("article", sa.Column("approver_sdhsv_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("article", "approver_sdhsv_id")
