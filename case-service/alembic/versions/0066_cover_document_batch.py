"""cover_document_batch table + article.batch_id FK

Revision ID: 0066_cover_document_batch
Revises: 0065_occupation_types
Create Date: 2026-06-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0066_cover_document_batch"
down_revision = "0065_occupation_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cover_document_batch",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("type_money_id", sa.Integer(), nullable=True),
        sa.Column("province_id", sa.Integer(), nullable=True),
        sa.Column("approver_sdhsv", sa.String(length=64), nullable=True),
        sa.Column("service_vsmart_id", sa.String(length=255), nullable=True),
        sa.Column("phone_service", sa.String(length=255), nullable=True),
        sa.Column("at", sa.String(length=255), nullable=True),
        sa.Column("date_at", sa.Date(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("refer_vsmart_id", sa.String(length=255), nullable=True),
        sa.Column("original_story", sa.Text(), nullable=True),
        sa.Column("fact_story", sa.Text(), nullable=True),
        sa.Column("laws", sa.Text(), nullable=True),
        sa.Column("consider", sa.Text(), nullable=True),
        sa.Column("suggestion", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["province_id"], ["province.id"], name=op.f("fk_cover_document_batch_province_id_province")),
        sa.ForeignKeyConstraint(["type_money_id"], ["type_money_category.id"], name=op.f("fk_cover_document_batch_type_money_id_type_money_category")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cover_document_batch")),
    )
    op.create_index(op.f("ix_cover_document_batch_province_id"), "cover_document_batch", ["province_id"], unique=False)
    op.create_index(op.f("ix_cover_document_batch_type_money_id"), "cover_document_batch", ["type_money_id"], unique=False)

    op.add_column("article", sa.Column("batch_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_article_batch_id"), "article", ["batch_id"], unique=False)
    op.create_foreign_key(
        op.f("fk_article_batch_id_cover_document_batch"),
        "article",
        "cover_document_batch",
        ["batch_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_article_batch_id_cover_document_batch"), "article", type_="foreignkey")
    op.drop_index(op.f("ix_article_batch_id"), table_name="article")
    op.drop_column("article", "batch_id")
    op.drop_index(op.f("ix_cover_document_batch_type_money_id"), table_name="cover_document_batch")
    op.drop_index(op.f("ix_cover_document_batch_province_id"), table_name="cover_document_batch")
    op.drop_table("cover_document_batch")
