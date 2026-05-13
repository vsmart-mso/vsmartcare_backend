"""update lookup master data and normalize case_number prefix

Revision ID: 0012_lookup_case_format
Revises: 0011_bank_name_applicant_fk
Create Date: 2026-05-13 00:00:00.000000

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_lookup_case_format"
down_revision: str | Sequence[str] | None = "0011_bank_name_applicant_fk"
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
    if set_cols:
        set_clause = ", ".join([f"{c} = EXCLUDED.{c}" for c in set_cols])
        sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({value_placeholders}) "
            f"ON CONFLICT (id) DO UPDATE SET {set_clause}"
        )
    else:
        sql = f"INSERT INTO {table} ({col_list}) VALUES ({value_placeholders}) ON CONFLICT (id) DO NOTHING"

    bind = op.get_bind()
    bind.execute(sa.text(sql), rows)


def upgrade() -> None:
    _upsert_by_id(
        "marital_status_types",
        [
            {"id": 6, "name": "สมรสเเยกกันอยู่"},
        ],
    )

    _upsert_by_id(
        "received_welfare_types",
        [
            {"id": 3, "name": "เงิน/เบี้ยผู้สูงอายุ (เบี้ยยังชีพผู้สูงอายุ)"},
            {"id": 4, "name": "เงิน/เบี้ยคนพิการ (เบี้ยความพิการ)"},
            {"id": 5, "name": "เงิน/เบี้ยเด็กแรกเกิด (เงินอุดหนุนเพื่อการเลี้ยงดูเด็กแรกเกิด)"},
            {"id": 7, "name": "การซ่อมบ้าน (เงินซ่อมแซมบ้าน)"},
            {"id": 11, "name": "เครื่องช่วยความพิการ"},
        ],
    )

    op.execute(
        sa.text(
            """
            UPDATE economic_infos
            SET housing_types_id = NULL
            WHERE housing_types_id = 4
            """
        )
    )
    op.execute(sa.text("DELETE FROM housing_types WHERE id = 4"))

    op.execute(
        sa.text(
            """
            DELETE FROM economic_income_sources AS removed
            USING economic_income_sources AS kept
            WHERE removed.economic_id = kept.economic_id
              AND removed.income_source_type_id = 4
              AND kept.income_source_type_id = 3
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE economic_income_sources
            SET income_source_type_id = 3
            WHERE income_source_type_id = 4
            """
        )
    )
    op.execute(sa.text("DELETE FROM income_source_types WHERE id = 4"))

    op.execute(
        sa.text(
            """
            UPDATE applicants
            SET case_number = 'CASE-' || substring(case_number FROM 6)
            WHERE case_number IS NOT NULL
              AND lower(left(case_number, 5)) = 'case-'
              AND left(case_number, 5) <> 'CASE-'
            """
        )
    )


def downgrade() -> None:
    _upsert_by_id(
        "housing_types",
        [
            {"id": 4, "name": "ที่พักชั่วคราว"},
        ],
    )
    _upsert_by_id(
        "income_source_types",
        [
            {"id": 4, "name": "เบี้ยยังชีพ/สวัสดิการรัฐ"},
        ],
    )
    _upsert_by_id(
        "received_welfare_types",
        [
            {"id": 3, "name": "เบี้ยผู้สูงอายุ (เบี้ยยังชีพผู้สูงอายุ)"},
            {"id": 4, "name": "เบี้ยความพิการ (เบี้ยความพิการ)"},
            {"id": 5, "name": "เงินเด็กแรกเกิด (เงินอุดหนุนเพื่อการเลี้ยงดูเด็กแรกเกิด)"},
            {"id": 7, "name": "เงินซ่อนบ้าน (เงินซ่อมแซมบ้าน)"},
            {"id": 11, "name": "เตรื่องช่วยความพิการ"},
        ],
    )
    op.execute(sa.text("DELETE FROM marital_status_types WHERE id = 6"))

    op.execute(
        sa.text(
            """
            UPDATE applicants
            SET case_number = 'case-' || substring(case_number FROM 6)
            WHERE case_number IS NOT NULL
              AND left(case_number, 5) = 'CASE-'
            """
        )
    )
