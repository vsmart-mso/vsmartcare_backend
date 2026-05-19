"""welfare_payment / file_payment: upload_batch_id for grouped upload history

Revision ID: 0034_upload_batch_id
Revises: 0033_welfare_payment_reject
Create Date: 2026-05-19 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0034_upload_batch_id"
down_revision: str | Sequence[str] | None = "0033_welfare_payment_reject"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IX_WP_UPLOAD_BATCH = "ix_welfare_payment_upload_batch_id"
IX_FP_UPLOAD_BATCH = "ix_file_payment_upload_batch_id"


def upgrade() -> None:
    batch_col = sa.Column("upload_batch_id", postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column("welfare_payment", batch_col)
    op.add_column("file_payment", batch_col)
    op.create_index(IX_WP_UPLOAD_BATCH, "welfare_payment", ["upload_batch_id"], unique=False)
    op.create_index(IX_FP_UPLOAD_BATCH, "file_payment", ["upload_batch_id"], unique=False)


def downgrade() -> None:
    op.drop_index(IX_FP_UPLOAD_BATCH, table_name="file_payment")
    op.drop_index(IX_WP_UPLOAD_BATCH, table_name="welfare_payment")
    op.drop_column("file_payment", "upload_batch_id")
    op.drop_column("welfare_payment", "upload_batch_id")
