"""payment intake v2: payment_method seed + case_payment

Revision ID: 0021_payment_method_case_payment
Revises: 0020_payment_intake_handling
Create Date: 2026-05-16 12:00:00.000000

transfer_money_type map (VSmart petition_form.type_payee_id_mso):
  False → cash | True → cheque | 0 → bank_transfer | 1 → promptpay
  2 → ktb_corporate | 3 → epayment
"""

from __future__ import annotations

import importlib.util
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0021_payment_method_case_payment"
down_revision: str | Sequence[str] | None = "0020_payment_intake_handling"
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
    op.create_table(
        "payment_method",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name_th", sa.String(length=255), nullable=False),
        sa.Column("legacy_vsmart_value", sa.String(length=10), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column(
            "requires_ktb_form",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_payment_method")),
        sa.UniqueConstraint("code", name=op.f("uq_payment_method_code")),
    )

    _upsert_by_id("payment_method", _load_vsmart_csv("payment_method.csv"))

    op.create_table(
        "case_payment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("case_handling_id", sa.Integer(), nullable=False),
        sa.Column("payment_method_id", sa.Integer(), nullable=False),
        sa.Column("receive_mode", sa.String(length=10), nullable=True),
        sa.Column("agent_person_id", sa.Integer(), nullable=True),
        sa.Column("payee_person_id", sa.Integer(), nullable=True),
        sa.Column("bank_name_id", sa.Integer(), nullable=True),
        sa.Column("bank_branch", sa.String(length=255), nullable=True),
        sa.Column("account_type", sa.String(length=100), nullable=True),
        sa.Column("account_number", sa.String(length=50), nullable=True),
        sa.Column("account_name", sa.String(length=255), nullable=True),
        sa.Column("cheque_reference", sa.String(length=100), nullable=True),
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
            "receive_mode IS NULL OR receive_mode IN ('self', 'agent')",
            name=op.f("ck_case_payment_receive_mode"),
        ),
        sa.ForeignKeyConstraint(
            ["agent_person_id"],
            ["persons.id"],
            name=op.f("fk_case_payment_agent_person_id_persons"),
        ),
        sa.ForeignKeyConstraint(
            ["bank_name_id"],
            ["bank_name.id"],
            name=op.f("fk_case_payment_bank_name_id_bank_name"),
        ),
        sa.ForeignKeyConstraint(
            ["case_handling_id"],
            ["case_handling.id"],
            name=op.f("fk_case_payment_case_handling_id_case_handling"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["payee_person_id"],
            ["persons.id"],
            name=op.f("fk_case_payment_payee_person_id_persons"),
        ),
        sa.ForeignKeyConstraint(
            ["payment_method_id"],
            ["payment_method.id"],
            name=op.f("fk_case_payment_payment_method_id_payment_method"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_case_payment")),
        sa.UniqueConstraint(
            "case_handling_id",
            name=op.f("uq_case_payment_case_handling_id"),
        ),
    )
    op.create_index(
        op.f("ix_case_payment_case_handling_id"),
        "case_payment",
        ["case_handling_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_case_payment_payment_method_id"),
        "case_payment",
        ["payment_method_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_case_payment_bank_name_id"),
        "case_payment",
        ["bank_name_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_case_payment_payee_person_id"),
        "case_payment",
        ["payee_person_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_case_payment_agent_person_id"),
        "case_payment",
        ["agent_person_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_case_payment_agent_person_id"), table_name="case_payment")
    op.drop_index(op.f("ix_case_payment_payee_person_id"), table_name="case_payment")
    op.drop_index(op.f("ix_case_payment_bank_name_id"), table_name="case_payment")
    op.drop_index(op.f("ix_case_payment_payment_method_id"), table_name="case_payment")
    op.drop_index(op.f("ix_case_payment_case_handling_id"), table_name="case_payment")
    op.drop_table("case_payment")
    op.drop_table("payment_method")
