"""add created_at/updated_at to mutable tables

Revision ID: 0009_audit_ts
Revises: 0007_seed_sd_pc
Create Date: 2026-05-09 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_audit_ts"
down_revision: str | Sequence[str] | None = "0007_seed_sd_pc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TABLES_ADD_BOTH = [
    "applicants",
    "dependency_loads",
    "economic_infos",
    "economic_income_sources",
    "welfare_request_types",
    "welfare_evidences",
    "welfare_histories",
    "welfare_histories_detail",
    "persons",
    "screening_logs",
    "welfare_request_consents",
]


def upgrade() -> None:
    # 1) Add columns
    for t in TABLES_ADD_BOTH:
        op.add_column(
            t,
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )
        op.add_column(
            t,
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
        )

    # welfare_request_status already has updated_at; add created_at only
    op.add_column(
        "welfare_request_status",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # 2) Create trigger function + triggers (idempotent)
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION set_updated_at_column()
            RETURNS trigger AS $$
            BEGIN
              NEW.updated_at = now();
              RETURN NEW;
            END;
            $$ language 'plpgsql';
            """
        )
    )

    for t in TABLES_ADD_BOTH + ["welfare_request_status"]:
        # asyncpg doesn't allow multiple commands per prepared statement,
        # so execute drop/create separately.
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_set_updated_at_{t} ON {t};"))
        op.execute(
            sa.text(
                f"""
                CREATE TRIGGER trg_set_updated_at_{t}
                BEFORE UPDATE ON {t}
                FOR EACH ROW
                EXECUTE FUNCTION set_updated_at_column();
                """
            )
        )


def downgrade() -> None:
    # Drop triggers first
    for t in TABLES_ADD_BOTH + ["welfare_request_status"]:
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS trg_set_updated_at_{t} ON {t};"))

    # Keep the function (shared) only if no table triggers remain.
    # For simplicity in downgrade, drop it unconditionally.
    op.execute(sa.text("DROP FUNCTION IF EXISTS set_updated_at_column();"))

    op.drop_column("welfare_request_status", "created_at")

    for t in reversed(TABLES_ADD_BOTH):
        op.drop_column(t, "updated_at")
        op.drop_column(t, "created_at")

