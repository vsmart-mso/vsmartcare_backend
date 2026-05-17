"""bank_name: bank_id_mso, bank_code, order + master data remap

Revision ID: 0025_bank_name_mso_code_order
Revises: 0024_economic_housing_rent
Create Date: 2026-05-17 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025_bank_name_mso_code_order"
down_revision: str | Sequence[str] | None = "0024_economic_housing_rent"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# id, name, bank_id_mso, bank_code, order
BANK_NAME_ROWS: list[dict] = [
    {"id": 1, "name": "ธนาคารเพื่อการเกษตรและสหกรณ์การเกษตร", "bank_id_mso": 0, "bank_code": "034", "order": 1},
    {"id": 2, "name": "ธนาคารออมสิน", "bank_id_mso": 18, "bank_code": "030", "order": 2},
    {"id": 3, "name": "ธนาคารกรุงไทย", "bank_id_mso": 3, "bank_code": "006", "order": 3},
    {"id": 4, "name": "ธนาคารไทยพาณิชย์", "bank_id_mso": 2, "bank_code": "014", "order": 4},
    {"id": 5, "name": "ธนาคารกรุงเทพ", "bank_id_mso": 22, "bank_code": "002", "order": 6},
    {"id": 6, "name": "ธนาคารกรุงศรีอยุธยา", "bank_id_mso": 5, "bank_code": "025", "order": 7},
    {"id": 7, "name": "ธนาคารกสิกรไทย", "bank_id_mso": 1, "bank_code": "004", "order": 5},
    {"id": 10, "name": "ธนาคารสแตนดาร์ดชาร์เตอร์ด (ไทย)", "bank_id_mso": 14, "bank_code": "020", "order": 10},
    {"id": 11, "name": "ธนาคารยูโอบี", "bank_id_mso": 12, "bank_code": "024", "order": 11},
    {"id": 12, "name": "ธนาคารทิสโก้", "bank_id_mso": 9, "bank_code": "067", "order": 12},
    {"id": 21, "name": "ธนาคารแห่งประเทศไทย", "bank_id_mso": 4, "bank_code": "000", "order": 13},
    {"id": 22, "name": "ธนาคารเกียรตินาคิน", "bank_id_mso": 6, "bank_code": "069", "order": 14},
    {"id": 23, "name": "ธนาคารซีไอเอ็มบีไทย", "bank_id_mso": 7, "bank_code": "022", "order": 15},
    {"id": 24, "name": "ธนาคารทหารไทย", "bank_id_mso": 8, "bank_code": "011", "order": 8},
    {"id": 25, "name": "ธนาคารไทยเครดิตเพื่อรายย่อย", "bank_id_mso": 10, "bank_code": "071", "order": 16},
    {"id": 26, "name": "ธนาคารธนชาต", "bank_id_mso": 11, "bank_code": "065", "order": 9},
    {"id": 27, "name": "ธนาคารแลนด์ แอนด์ เฮาส์", "bank_id_mso": 13, "bank_code": "073", "order": 17},
    {
        "id": 28,
        "name": "ธนาคารพัฒนาวิสาหกิจขนาดกลางและขนาดย่อมแห่งประเทศไทย",
        "bank_id_mso": 15,
        "bank_code": "098",
        "order": 18,
    },
    {"id": 29, "name": "ธนาคารเพื่อการส่งออกและนำเข้าแห่งประเทศไทย", "bank_id_mso": 17, "bank_code": "035", "order": 19},
    {"id": 30, "name": "ธนาคารอาคารสงเคราะห์", "bank_id_mso": 19, "bank_code": "033", "order": 20},
    {"id": 31, "name": "ธนาคารอิสลามแห่งประเทศไทย", "bank_id_mso": 20, "bank_code": "066", "order": 21},
    {"id": 32, "name": "ธนาคารไอซีบีซี (ไทย)", "bank_id_mso": 21, "bank_code": "070", "order": 22},
    {"id": 33, "name": "ธนาคารทหารไทยธนชาติ จำกัด", "bank_id_mso": 0, "bank_code": "011", "order": 8},
]

# แมป id เดิม (0011 seed) -> id ใหม่
_OLD_BANK_ID_TO_NEW: dict[int, int] = {
    1: 3,   # กรุงไทย
    2: 5,   # กรุงเทพ
    3: 7,   # กสิกร
    4: 4,   # ไทยพาณิชย์
    5: 2,   # ออมสิน
    6: 1,   # ธ.ก.ส.
    7: 6,   # กรุงศรี
    8: 33,  # ทหารไทยธนชาต (ttb)
}

_BANK_FK_TABLES: list[tuple[str, str, str]] = [
    ("applicants", "bank_name_id", "fk_applicants_bank_name_id_bank_name"),
    ("case_payment", "bank_name_id", "fk_case_payment_bank_name_id_bank_name"),
    (
        "case_ktb_corporate",
        "payroll_bank_name_id",
        "fk_case_ktb_corporate_payroll_bank_name_id_bank_name",
    ),
    (
        "case_ktb_corporate",
        "other_bank_name_id",
        "fk_case_ktb_corporate_other_bank_name_id_bank_name",
    ),
]


def _upsert_by_id(table: str, rows: list[dict]) -> None:
    if not rows:
        return
    cols = [k for k in rows[0].keys()]
    if "id" not in cols:
        raise ValueError("seed rows must include id")

    col_list = ", ".join(f'"{c}"' if c == "order" else c for c in cols)
    value_placeholders = ", ".join([f":{c}" for c in cols])

    set_cols = [c for c in cols if c != "id"]
    if set_cols:
        set_clause = ", ".join(
            [f'"{c}" = EXCLUDED."{c}"' if c == "order" else f"{c} = EXCLUDED.{c}" for c in set_cols]
        )
        sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({value_placeholders}) "
            f"ON CONFLICT (id) DO UPDATE SET {set_clause}"
        )
    else:
        sql = f"INSERT INTO {table} ({col_list}) VALUES ({value_placeholders}) ON CONFLICT (id) DO NOTHING"

    bind = op.get_bind()
    bind.execute(sa.text(sql), rows)


def _remap_bank_fk_column(table: str, column: str) -> None:
    case_lines = ["CASE"]
    for old_id, new_id in _OLD_BANK_ID_TO_NEW.items():
        case_lines.append(f"WHEN {column} = {old_id} THEN {9000 + old_id}")
    case_lines.append(f"ELSE {column}")
    case_lines.append("END")
    temp_expr = "\n                ".join(case_lines)

    op.execute(
        sa.text(
            f"""
            UPDATE {table}
            SET {column} = {temp_expr}
            WHERE {column} IN ({", ".join(str(i) for i in _OLD_BANK_ID_TO_NEW)})
            """
        )
    )

    new_case_lines = ["CASE"]
    for old_id, new_id in _OLD_BANK_ID_TO_NEW.items():
        new_case_lines.append(f"WHEN {column} = {9000 + old_id} THEN {new_id}")
    new_case_lines.append(f"ELSE {column}")
    new_case_lines.append("END")
    new_expr = "\n                ".join(new_case_lines)

    op.execute(
        sa.text(
            f"""
            UPDATE {table}
            SET {column} = {new_expr}
            WHERE {column} IN ({", ".join(str(9000 + i) for i in _OLD_BANK_ID_TO_NEW)})
            """
        )
    )


def upgrade() -> None:
    op.add_column("bank_name", sa.Column("bank_id_mso", sa.Integer(), nullable=True))
    op.add_column("bank_name", sa.Column("bank_code", sa.String(length=10), nullable=True))
    op.add_column("bank_name", sa.Column("order", sa.Integer(), nullable=True))

    for table, column, constraint in _BANK_FK_TABLES:
        op.drop_constraint(constraint, table, type_="foreignkey")
        _remap_bank_fk_column(table, column)

    op.execute(sa.text("DELETE FROM bank_name"))

    _upsert_by_id("bank_name", BANK_NAME_ROWS)

    op.alter_column("bank_name", "bank_id_mso", nullable=False)
    op.alter_column("bank_name", "bank_code", nullable=False)
    op.alter_column("bank_name", "order", nullable=False)

    for table, column, constraint in _BANK_FK_TABLES:
        op.create_foreign_key(
            constraint,
            table,
            "bank_name",
            [column],
            ["id"],
        )


def downgrade() -> None:
    _NEW_TO_OLD: dict[int, int] = {v: k for k, v in _OLD_BANK_ID_TO_NEW.items()}

    for table, column, constraint in _BANK_FK_TABLES:
        op.drop_constraint(constraint, table, type_="foreignkey")

    for table, column, _ in _BANK_FK_TABLES:
        case_lines = ["CASE"]
        for new_id, old_id in _NEW_TO_OLD.items():
            case_lines.append(f"WHEN {column} = {new_id} THEN {9000 + old_id}")
        case_lines.append(f"ELSE {column}")
        case_lines.append("END")
        temp_expr = "\n                ".join(case_lines)

        op.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET {column} = {temp_expr}
                WHERE {column} IN ({", ".join(str(i) for i in _NEW_TO_OLD)})
                """
            )
        )

        rev_case_lines = ["CASE"]
        for new_id, old_id in _NEW_TO_OLD.items():
            rev_case_lines.append(f"WHEN {column} = {9000 + old_id} THEN {old_id}")
        rev_case_lines.append(f"ELSE {column}")
        rev_case_lines.append("END")
        rev_expr = "\n                ".join(rev_case_lines)

        op.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET {column} = {rev_expr}
                WHERE {column} IN ({", ".join(str(9000 + i) for i in _NEW_TO_OLD)})
                """
            )
        )

    op.execute(sa.text("DELETE FROM bank_name"))

    op.drop_column("bank_name", "order")
    op.drop_column("bank_name", "bank_code")
    op.drop_column("bank_name", "bank_id_mso")

    _upsert_by_id(
        "bank_name",
        [
            {"id": 1, "name": "ธนาคารกรุงไทย"},
            {"id": 2, "name": "ธนาคารกรุงเทพ"},
            {"id": 3, "name": "ธนาคารกสิกรไทย"},
            {"id": 4, "name": "ธนาคารไทยพาณิชย์"},
            {"id": 5, "name": "ธนาคารออมสิน"},
            {"id": 6, "name": "ธนาคารเพื่อการเกษตรเเละสหกรณ์การเกษตร (ธ.ก.ส)"},
            {"id": 7, "name": "ธนาคารกรุงศรีอยุธยา"},
            {"id": 8, "name": "ธนาคารทหารไทยธนชาต (ttb)"},
        ],
    )

    for table, column, constraint in _BANK_FK_TABLES:
        op.create_foreign_key(
            constraint,
            table,
            "bank_name",
            [column],
            ["id"],
        )
