"""welfare_payment / file_payment: upload_batch_id for grouped upload history

Revision ID: 0034_upload_batch_id
Revises: 0034_ocr_results
Create Date: 2026-05-19 12:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0034_upload_batch_id"
down_revision: str | Sequence[str] | None = "0034_ocr_results"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

IX_WP_UPLOAD_BATCH = "ix_welfare_payment_upload_batch_id"
IX_FP_UPLOAD_BATCH = "ix_file_payment_upload_batch_id"

_TABLES = ("welfare_payment", "file_payment")


def _column_names(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {col["name"] for col in inspector.get_columns(table)}


def _index_names(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {idx["name"] for idx in inspector.get_indexes(table)}


def upgrade() -> None:
    for table in _TABLES:
        if "upload_batch_id" not in _column_names(table):
            op.add_column(
                table,
                sa.Column("upload_batch_id", postgresql.UUID(as_uuid=True), nullable=True),
            )
    if IX_WP_UPLOAD_BATCH not in _index_names("welfare_payment"):
        op.create_index(IX_WP_UPLOAD_BATCH, "welfare_payment", ["upload_batch_id"], unique=False)
    if IX_FP_UPLOAD_BATCH not in _index_names("file_payment"):
        op.create_index(IX_FP_UPLOAD_BATCH, "file_payment", ["upload_batch_id"], unique=False)


def downgrade() -> None:
    if IX_FP_UPLOAD_BATCH in _index_names("file_payment"):
        op.drop_index(IX_FP_UPLOAD_BATCH, table_name="file_payment")
    if IX_WP_UPLOAD_BATCH in _index_names("welfare_payment"):
        op.drop_index(IX_WP_UPLOAD_BATCH, table_name="welfare_payment")
    for table in _TABLES:
        if "upload_batch_id" in _column_names(table):
            op.drop_column(table, "upload_batch_id")
