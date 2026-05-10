"""seed master geo data (province; later: districts/sub_districts/postcode mapping)

Revision ID: 0003_seed_master_geo_data
Revises: 0002_seed_master_data
Create Date: 2026-05-09 00:00:00.000000

Source: phpMyAdmin dump (MariaDB) province list (TH/EN). We store Thai name in `province.name`.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0003_seed_master_geo_data"
down_revision: str | Sequence[str] | None = "0002_seed_master_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _upsert_by_id(table: str, rows: list[dict]) -> None:
    """
    Postgres upsert by `id` to make seed idempotent.

    Assumes every row has `id` key.
    """
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
        sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({value_placeholders}) "
            f"ON CONFLICT (id) DO NOTHING"
        )

    bind = op.get_bind()
    bind.execute(sa.text(sql), rows)


def _read_copy_rows(seed_path: Path, copy_table: str) -> list[dict[str, str | None]]:
    """
    Read rows from pg_dump plain SQL: COPY public.<table> (cols...) FROM stdin;
    Data lines are tab-separated; NULL is represented as \\N; block ends with \\.
    """
    rows: list[dict[str, str | None]] = []
    in_copy = False
    cols: list[str] = []

    with seed_path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not in_copy:
                prefix = f"COPY public.{copy_table} "
                if line.startswith(prefix) and " FROM stdin;" in line:
                    # COPY public.table (a, b, c) FROM stdin;
                    start = line.find("(")
                    end = line.find(")", start + 1)
                    cols = [c.strip() for c in line[start + 1 : end].split(",")]
                    in_copy = True
                continue

            if line == r"\.":
                break

            values = line.split("\t")
            if len(values) != len(cols):
                continue
            row: dict[str, str | None] = {}
            for c, v in zip(cols, values, strict=True):
                row[c] = None if v == r"\N" else v
            rows.append(row)

    if not cols:
        raise RuntimeError(f"COPY block for public.{copy_table} not found in {seed_path}")
    return rows


def upgrade() -> None:
    seed_path = (
        Path(__file__).resolve().parent.parent / "seed_data" / "geo" / "province.sql"
    )

    # This migration expects a plain-text SQL dump (INSERT ... VALUES (...), ...).
    # If you re-dumped using `pg_dump` custom format, it will start with "PGDMP" and is not parsable here.
    header = seed_path.read_bytes()[:5]
    if header == b"PGDMP":
        raise RuntimeError(
            f"{seed_path} looks like a pg_dump custom-format file (PGDMP). "
            "Please re-export as plain SQL (text) with INSERT/COPY statements."
        )

    src_rows = _read_copy_rows(seed_path, "petition_form_province")
    rows: list[dict] = []
    for r in src_rows:
        if r.get("id") is None or r.get("name") is None:
            continue
        pid = int(r["id"])
        code = r.get("code")
        rows.append(
            {
                "id": pid,
                "code": str(code if code is not None else pid),
                "name": str(r["name"]),
            }
        )

    _upsert_by_id("province", rows)


def downgrade() -> None:
    seed_path = (
        Path(__file__).resolve().parent.parent / "seed_data" / "geo" / "province.sql"
    )

    header = seed_path.read_bytes()[:5]
    if header == b"PGDMP":
        raise RuntimeError(
            f"{seed_path} looks like a pg_dump custom-format file (PGDMP). "
            "Please re-export as plain SQL (text) to downgrade seeded data."
        )

    src_rows = _read_copy_rows(seed_path, "petition_form_province")
    ids = [int(r["id"]) for r in src_rows if r.get("id") is not None]

    if ids:
        op.execute(
            sa.text("DELETE FROM province WHERE id IN :ids").bindparams(
                sa.bindparam("ids", expanding=True)
            ),
            {"ids": ids},
        )
