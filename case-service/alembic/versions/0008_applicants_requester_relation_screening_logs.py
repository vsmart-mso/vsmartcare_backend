"""applicants: case_number + requester_relation_id; screening_logs slim schema

- requester_relation_type master + seed (1, ตนเอง)
- applicants: drop approve, user_sdshv_approve, requester_relation string
- screening_logs: drop audit timestamps and screening_result; widen string cols

Revision ID: 0008_app_req_rel_scr
Revises: 0007_seed_sd_pc
Create Date: 2026-05-10 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_app_req_rel_scr"
down_revision: str | Sequence[str] | None = "0007_seed_sd_pc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- screening_logs: remove updated_at trigger / audit columns / screening_result ---
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_set_updated_at_screening_logs ON screening_logs;"))

    op.drop_column("screening_logs", "updated_at")
    op.drop_column("screening_logs", "created_at")
    op.drop_column("screening_logs", "screening_result")

    op.alter_column(
        "screening_logs",
        "criteria_version",
        existing_type=sa.String(length=50),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "screening_logs",
        "failure_reason_code",
        existing_type=sa.String(length=100),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
    op.alter_column(
        "screening_logs",
        "ip_address",
        existing_type=sa.String(length=45),
        type_=sa.String(length=255),
        existing_nullable=True,
    )

    # --- requester_relation_type + applicants ---
    op.create_table(
        "requester_relation_type",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_requester_relation_type")),
    )
    op.execute(sa.text("INSERT INTO requester_relation_type (id, name) VALUES (1, 'ตนเอง')"))
    op.execute(
        sa.text(
            "SELECT setval("
            "pg_get_serial_sequence('requester_relation_type', 'id'),"
            " (SELECT COALESCE(MAX(id), 1) FROM requester_relation_type)"
            ")"
        )
    )

    op.add_column("applicants", sa.Column("case_number", sa.String(length=100), nullable=True))
    op.add_column(
        "applicants",
        sa.Column("requester_relation_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_applicants_requester_relation_id_requester_relation_type"),
        "applicants",
        "requester_relation_type",
        ["requester_relation_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_applicants_requester_relation_id"),
        "applicants",
        ["requester_relation_id"],
        unique=False,
    )

    op.execute(sa.text("UPDATE applicants SET requester_relation_id = 1"))
    op.alter_column(
        "applicants",
        "requester_relation_id",
        existing_type=sa.Integer(),
        nullable=False,
        existing_nullable=True,
    )

    op.drop_column("applicants", "requester_relation")
    op.drop_column("applicants", "approve")
    op.drop_column("applicants", "user_sdshv_approve")


def downgrade() -> None:
    op.add_column(
        "applicants",
        sa.Column("user_sdshv_approve", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "applicants",
        sa.Column(
            "approve",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "applicants",
        sa.Column("requester_relation", sa.String(length=100), nullable=True),
    )

    op.execute(
        sa.text(
            """
            UPDATE applicants a
            SET requester_relation = r.name
            FROM requester_relation_type r
            WHERE a.requester_relation_id = r.id
            """
        )
    )

    op.drop_constraint(
        op.f("fk_applicants_requester_relation_id_requester_relation_type"),
        "applicants",
        type_="foreignkey",
    )
    op.drop_index(op.f("ix_applicants_requester_relation_id"), table_name="applicants")
    op.drop_column("applicants", "requester_relation_id")
    op.drop_column("applicants", "case_number")

    op.drop_table("requester_relation_type")

    op.alter_column(
        "screening_logs",
        "ip_address",
        existing_type=sa.String(length=255),
        type_=sa.String(length=45),
        existing_nullable=True,
    )
    op.alter_column(
        "screening_logs",
        "failure_reason_code",
        existing_type=sa.String(length=255),
        type_=sa.String(length=100),
        existing_nullable=True,
    )
    op.alter_column(
        "screening_logs",
        "criteria_version",
        existing_type=sa.String(length=255),
        type_=sa.String(length=50),
        existing_nullable=True,
    )

    op.add_column("screening_logs", sa.Column("screening_result", sa.String(length=100), nullable=True))
    op.add_column(
        "screening_logs",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "screening_logs",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.execute(
        sa.text(
            """
            CREATE TRIGGER trg_set_updated_at_screening_logs
            BEFORE UPDATE ON screening_logs
            FOR EACH ROW
            EXECUTE FUNCTION set_updated_at_column();
            """
        )
    )
