"""add money category and payment tables

Revision ID: 0013_money_category_payment
Revises: 0012_lookup_case_format
Create Date: 2026-05-14 23:45:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_money_category_payment"
down_revision: str | Sequence[str] | None = "0012_lookup_case_format"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


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
        "type_money_category",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("name_acronym", sa.String(length=255), nullable=False),
        sa.Column("color", sa.String(length=32), nullable=False),
        sa.Column("name_acrovym_eng", sa.String(length=255), nullable=False),
        sa.Column(
            "activate",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_type_money_category")),
    )

    _upsert_by_id(
        "type_money_category",
        [
            {
                "id": 1,
                "name": "เงินอุดหนุนเพื่อช่วยเหลือผู้ประสบปัญหาทางสังคมกรณีฉุกเฉิน",
                "name_acronym": "สป.",
                "color": "#ff4d79",
                "name_acrovym_eng": "mso",
                "activate": True,
            },
            {
                "id": 2,
                "name": "เงินสงเคราะห์เด็กในครอบครัวยากจน",
                "name_acronym": "ดย.",
                "color": "#fa6400",
                "name_acrovym_eng": "dcy",
                "activate": True,
            },
            {
                "id": 3,
                "name": "เงินสงเคราะห์และฟื้นฟูสมรรถภาพคนพิการ",
                "name_acronym": "พก.",
                "color": "#14b1ff",
                "name_acrovym_eng": "dep",
                "activate": True,
            },
            {
                "id": 4,
                "name": "เงินสงเคราะห์ผู้สูงอายุในภาวะยากลำบาก",
                "name_acronym": "ผส.",
                "color": "#ffc800",
                "name_acrovym_eng": "dop",
                "activate": True,
            },
            {
                "id": 5,
                "name": "เงินอุดหนุนเงินสงเคราะห์ผู้มีรายได้น้อยและผู้ไร้ที่พึ่ง",
                "name_acronym": "พส.",
                "color": "#00b300",
                "name_acrovym_eng": "dsdw",
                "activate": True,
            },
            {
                "id": 6,
                "name": "เงินสงเคราะห์สตรีหรือครอบครัวที่ประสบปัญหาทางสังคม",
                "name_acronym": "สค.",
                "color": "#ff94f2",
                "name_acrovym_eng": "dwf",
                "activate": True,
            },
        ],
    )

    op.add_column(
        "applicants",
        sa.Column("type_money_category_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "applicants",
        sa.Column("sw_explorer_sdshv", sa.String(length=255), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_applicants_type_money_category_id_type_money_category"),
        "applicants",
        "type_money_category",
        ["type_money_category_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_applicants_type_money_category_id"),
        "applicants",
        ["type_money_category_id"],
        unique=False,
    )

    op.create_table(
        "approve_case",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column(
            "approve_status",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("esignature", sa.String(length=1024), nullable=True),
        sa.Column("user_sdshv", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_approve_case_applicant_id_applicants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_approve_case")),
    )
    op.create_index(
        op.f("ix_approve_case_applicant_id"),
        "approve_case",
        ["applicant_id"],
        unique=False,
    )

    op.create_table(
        "welfare_dda_ref",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dda_ref", sa.String(length=255), nullable=False),
        sa.Column("user_sdshv", sa.String(length=255), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_welfare_dda_ref")),
    )

    op.create_table(
        "welfare_payment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("applicant_id", sa.Integer(), nullable=False),
        sa.Column(
            "is_037_or_038",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("dda_ref_id", sa.Integer(), nullable=False),
        sa.Column("payment_number", sa.String(length=255), nullable=True),
        sa.Column("payment_038_reason", sa.String(length=255), nullable=True),
        sa.Column("user_sdshv", sa.String(length=255), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["applicant_id"],
            ["applicants.id"],
            name=op.f("fk_welfare_payment_applicant_id_applicants"),
        ),
        sa.ForeignKeyConstraint(
            ["dda_ref_id"],
            ["welfare_dda_ref.id"],
            name=op.f("fk_welfare_payment_dda_ref_id_welfare_dda_ref"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_welfare_payment")),
    )
    op.create_index(
        op.f("ix_welfare_payment_applicant_id"),
        "welfare_payment",
        ["applicant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_welfare_payment_dda_ref_id"),
        "welfare_payment",
        ["dda_ref_id"],
        unique=False,
    )

    op.create_table(
        "file_payment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("welfare_dda_ref_id", sa.Integer(), nullable=False),
        sa.Column("file_original_name", sa.String(length=255), nullable=True),
        sa.Column("file_stored_name", sa.String(length=255), nullable=True),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("file_width", sa.Integer(), nullable=True),
        sa.Column("file_height", sa.Integer(), nullable=True),
        sa.Column("attachment_type_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["attachment_type_id"],
            ["attachment_types.id"],
            name=op.f("fk_file_payment_attachment_type_id_attachment_types"),
        ),
        sa.ForeignKeyConstraint(
            ["welfare_dda_ref_id"],
            ["welfare_dda_ref.id"],
            name=op.f("fk_file_payment_welfare_dda_ref_id_welfare_dda_ref"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_file_payment")),
    )
    op.create_index(
        op.f("ix_file_payment_attachment_type_id"),
        "file_payment",
        ["attachment_type_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_file_payment_welfare_dda_ref_id"),
        "file_payment",
        ["welfare_dda_ref_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_file_payment_welfare_dda_ref_id"), table_name="file_payment")
    op.drop_index(op.f("ix_file_payment_attachment_type_id"), table_name="file_payment")
    op.drop_table("file_payment")

    op.drop_index(op.f("ix_welfare_payment_dda_ref_id"), table_name="welfare_payment")
    op.drop_index(op.f("ix_welfare_payment_applicant_id"), table_name="welfare_payment")
    op.drop_table("welfare_payment")

    op.drop_table("welfare_dda_ref")

    op.drop_index(op.f("ix_approve_case_applicant_id"), table_name="approve_case")
    op.drop_table("approve_case")

    op.drop_index(op.f("ix_applicants_type_money_category_id"), table_name="applicants")
    op.drop_constraint(
        op.f("fk_applicants_type_money_category_id_type_money_category"),
        "applicants",
        type_="foreignkey",
    )
    op.drop_column("applicants", "sw_explorer_sdshv")
    op.drop_column("applicants", "type_money_category_id")

    op.drop_table("type_money_category")
