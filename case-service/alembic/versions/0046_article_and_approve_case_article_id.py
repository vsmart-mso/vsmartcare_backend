"""สร้างตาราง article (1:1 applicants) และ approve_case.article_id.

Revision ID: 0046_article_and_approve_case_article_id
Revises: 0045_merge_0044_heads
Create Date: 2026-05-25 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0046_article_and_approve_case_article_id"
down_revision: str | Sequence[str] | None = "0045_merge_0044_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "article",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
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
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_article_applicant_id_applicants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_article")),
        sa.UniqueConstraint("applicant_id", name=op.f("uq_article_applicant_id")),
    )
    op.create_index(
        op.f("ix_article_applicant_id"),
        "article",
        ["applicant_id"],
        unique=True,
    )

    op.add_column("approve_case", sa.Column("article_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_approve_case_article_id_article"),
        "approve_case",
        "article",
        ["article_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_approve_case_article_id"),
        "approve_case",
        ["article_id"],
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_approve_case_article_id"), table_name="approve_case")
    op.drop_constraint(
        op.f("fk_approve_case_article_id_article"),
        "approve_case",
        type_="foreignkey",
    )
    op.drop_column("approve_case", "article_id")
    op.drop_index(op.f("ix_article_applicant_id"), table_name="article")
    op.drop_table("article")
