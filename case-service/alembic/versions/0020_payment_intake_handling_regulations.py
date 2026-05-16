"""payment intake v2: case_handling, announcement_regulations, case_regulation_choice

Revision ID: 0020_payment_intake_handling
Revises: 0020_merge_0019_heads
Create Date: 2026-05-16 12:00:00.000000
"""

from __future__ import annotations

import importlib.util
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0020_payment_intake_handling"
down_revision: str | Sequence[str] | None = "0020_merge_0019_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _load_vsmart_csv(filename: str) -> list[dict]:
    seed_dir = Path(__file__).resolve().parents[1] / "seed_data" / "vsmart"
    loader_path = seed_dir / "load_csv.py"
    spec = importlib.util.spec_from_file_location("vsmart_load_csv", loader_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load VSmart CSV loader: {loader_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_vsmart_csv(filename)


def _upsert_by_id(table: str, rows: list[dict]) -> None:
    if not rows:
        return

    cols = [k for k in rows[0].keys()]
    if "id" not in cols:
        raise ValueError("seed rows must include id")

    col_list = ", ".join(cols)
    value_placeholders = ", ".join([f":{c}" for c in cols])
    set_cols = [c for c in cols if c != "id"]
    set_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in set_cols])

    sql = (
        f"INSERT INTO {table} ({col_list}) VALUES ({value_placeholders}) "
        f"ON CONFLICT (id) DO UPDATE SET {set_clause}"
    )
    op.get_bind().execute(sa.text(sql), rows)


def upgrade() -> None:
    _upsert_by_id(
        "type_money_category",
        _load_vsmart_csv("type_money_category_extra.csv"),
    )

    op.create_table(
        "case_handling",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("vsmart_informer_id", sa.Integer(), nullable=True),
        sa.Column("vsmart_social_worker_id", sa.Integer(), nullable=True),
        sa.Column("sw_user_sdshv", sa.String(length=255), nullable=True),
        sa.Column("intake_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_case_handling_applicant_id_applicants"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_handling")),
        sa.UniqueConstraint("applicant_id", name=op.f("uq_case_handling_applicant_id")),
    )
    op.create_index(
        op.f("ix_case_handling_applicant_id"),
        "case_handling",
        ["applicant_id"],
        unique=True,
    )

    op.create_table(
        "announcement_regulations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("short_name", sa.String(length=100), nullable=True),
        sa.Column("type_money_category_id", sa.Integer(), nullable=False),
        sa.Column("maximum_money", sa.Numeric(12, 2), nullable=False),
        sa.Column("limit_per_budget_year", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=True),
        sa.Column(
            "activate",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("vsmart_legacy_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["type_money_category_id"],
            ["type_money_category.id"],
            name=op.f(
                "fk_announcement_regulations_type_money_category_id_type_money_category"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_announcement_regulations")),
        sa.UniqueConstraint("code", name=op.f("uq_announcement_regulations_code")),
    )
    op.create_index(
        op.f("ix_announcement_regulations_type_money_category_id"),
        "announcement_regulations",
        ["type_money_category_id"],
        unique=False,
    )

    _upsert_by_id(
        "announcement_regulations",
        _load_vsmart_csv("announcement_regulations.csv"),
    )

    op.create_table(
        "case_regulation_choice",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_handling_id", sa.Integer(), nullable=False),
        sa.Column("regulation_id", sa.Integer(), nullable=False),
        sa.Column(
            "help_kind",
            sa.String(length=10),
            nullable=False,
            server_default="money",
        ),
        sa.Column("money_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("esignature", sa.Text(), nullable=True),
        sa.Column("signed_by_sdshv", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "help_kind IN ('money', 'things')",
            name=op.f("ck_case_regulation_choice_help_kind"),
        ),
        sa.ForeignKeyConstraint(
            ["case_handling_id"],
            ["case_handling.id"],
            name=op.f("fk_case_regulation_choice_case_handling_id_case_handling"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["regulation_id"],
            ["announcement_regulations.id"],
            name=op.f(
                "fk_case_regulation_choice_regulation_id_announcement_regulations"
            ),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_regulation_choice")),
        sa.UniqueConstraint(
            "case_handling_id",
            name=op.f("uq_case_regulation_choice_case_handling_id"),
        ),
    )
    op.create_index(
        op.f("ix_case_regulation_choice_case_handling_id"),
        "case_regulation_choice",
        ["case_handling_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_case_regulation_choice_regulation_id"),
        "case_regulation_choice",
        ["regulation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_case_regulation_choice_regulation_id"),
        table_name="case_regulation_choice",
    )
    op.drop_index(
        op.f("ix_case_regulation_choice_case_handling_id"),
        table_name="case_regulation_choice",
    )
    op.drop_table("case_regulation_choice")

    op.drop_index(
        op.f("ix_announcement_regulations_type_money_category_id"),
        table_name="announcement_regulations",
    )
    op.drop_table("announcement_regulations")

    op.drop_index(op.f("ix_case_handling_applicant_id"), table_name="case_handling")
    op.drop_table("case_handling")

    op.execute(
        sa.text("DELETE FROM type_money_category WHERE id IN (7, 8)")
    )
