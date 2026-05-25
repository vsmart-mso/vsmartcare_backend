"""more_mso (1:1 case_handling), type_send master + seed, send_data (N:1 applicants, type_send)

Revision ID: 0043_mso_type_send
Revises: 0042_applicant_bank_extra
Create Date: 2026-05-25 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0043_mso_type_send"
down_revision: str | Sequence[str] | None = "0042_applicant_bank_extra"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TYPE_SEND_ROWS: list[dict] = [
    {"id": 1, "name": "ส่งต่อเข้าหระทรวง", "detail": None},
    {"id": 2, "name": "ส่งต่อ mso logbook", "detail": None},
]


def _widen_alembic_version_column() -> None:
    """Alembic default version_num is VARCHAR(32); revision ids may exceed that."""
    op.execute(
        sa.text(
            "ALTER TABLE alembic_version "
            "ALTER COLUMN version_num TYPE VARCHAR(128)"
        )
    )


def _upsert_by_id(table: str, rows: list[dict]) -> None:
    if not rows:
        return

    cols = list(rows[0].keys())
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
    _widen_alembic_version_column()

    op.create_table(
        "type_send",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_type_send")),
    )
    _upsert_by_id("type_send", TYPE_SEND_ROWS)
    op.execute(
        sa.text(
            "SELECT setval(pg_get_serial_sequence('type_send', 'id'), "
            "(SELECT COALESCE(MAX(id), 1) FROM type_send))"
        )
    )

    op.create_table(
        "more_mso",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_handling_id", sa.Integer(), nullable=False),
        sa.Column("follow_date", sa.String(length=255), nullable=True),
        sa.Column("help_number", sa.String(length=255), nullable=True),
        sa.Column("help_date", sa.Date(), nullable=True),
        sa.Column("appove_name", sa.String(length=255), nullable=True),
        sa.Column("appove_number", sa.String(length=255), nullable=True),
        sa.Column("appove_date", sa.Date(), nullable=True),
        sa.Column("receive_date", sa.Date(), nullable=True),
        sa.Column("cashier", sa.String(length=255), nullable=True),
        sa.Column("cashier_name", sa.String(length=255), nullable=True),
        sa.Column("follower_name", sa.String(length=255), nullable=True),
        sa.Column(
            "follower_position_vsmart_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "follower_department_vsmart_id",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column("follower_tel", sa.String(length=255), nullable=True),
        sa.Column("follower_date", sa.Date(), nullable=True),
        sa.Column("follower_result", sa.Text(), nullable=True),
        sa.Column("follower_method", sa.Integer(), nullable=True),
        sa.Column("follower_type", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["case_handling_id"],
            ["case_handling.id"],
            name=op.f("fk_more_mso_case_handling_id_case_handling"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_more_mso")),
        sa.UniqueConstraint(
            "case_handling_id",
            name=op.f("uq_more_mso_case_handling_id"),
        ),
    )
    op.create_index(
        op.f("ix_more_mso_case_handling_id"),
        "more_mso",
        ["case_handling_id"],
        unique=True,
    )

    op.create_table(
        "send_data",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("send_by_sdshv", sa.String(length=255), nullable=True),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column("type_send_id", sa.Integer(), nullable=False),
        sa.Column("json_case", sa.JSON(), nullable=True),
        sa.Column("response_code", sa.String(length=255), nullable=True),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_send_data_applicant_id_applicants"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["type_send_id"],
            ["type_send.id"],
            name=op.f("fk_send_data_type_send_id_type_send"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_send_data")),
    )
    op.create_index(
        op.f("ix_send_data_applicant_id"),
        "send_data",
        ["applicant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_send_data_type_send_id"),
        "send_data",
        ["type_send_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_send_data_type_send_id"), table_name="send_data")
    op.drop_index(op.f("ix_send_data_applicant_id"), table_name="send_data")
    op.drop_table("send_data")
    op.drop_index(op.f("ix_more_mso_case_handling_id"), table_name="more_mso")
    op.drop_table("more_mso")
    op.drop_table("type_send")
    op.execute(
        sa.text(
            "ALTER TABLE alembic_version "
            "ALTER COLUMN version_num TYPE VARCHAR(32)"
        )
    )
