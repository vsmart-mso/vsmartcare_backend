"""seed master geo data (sub_districts)

Revision ID: 0005_seed_geo_subdistricts
Revises: 0004_seed_geo_districts
Create Date: 2026-05-09 00:00:00.000000

Source: phpMyAdmin dump (MariaDB) subdistrict list (TH). We store Thai name in `sub_districts.name`.
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0005_seed_geo_subdistricts"
down_revision: str | Sequence[str] | None = "0004_seed_geo_districts"
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
        sql = (
            f"INSERT INTO {table} ({col_list}) VALUES ({value_placeholders}) "
            f"ON CONFLICT (id) DO NOTHING"
        )

    op.get_bind().execute(sa.text(sql), rows)


def _read_copy_rows(seed_path: Path, copy_table: str) -> list[dict[str, str | None]]:
    rows: list[dict[str, str | None]] = []
    in_copy = False
    cols: list[str] = []
    with seed_path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not in_copy:
                prefix = f"COPY public.{copy_table} "
                if line.startswith(prefix) and " FROM stdin;" in line:
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
        Path(__file__).resolve().parent.parent
        / "seed_data"
        / "geo"
        / "subdistricts.sql"
    )

    header = seed_path.read_bytes()[:5]
    if header == b"PGDMP":
        raise RuntimeError(
            f"{seed_path} looks like a pg_dump custom-format file (PGDMP). "
            "Please re-export as plain SQL (text) with INSERT/COPY statements."
        )

    src_rows = _read_copy_rows(seed_path, "petition_form_sub_district")
    rows: list[dict] = []
    district_ids: set[int] = set()
    for r in src_rows:
        if (
            r.get("id") is None
            or r.get("name") is None
            or r.get("district_id_id") is None
        ):
            continue
        sid = int(r["id"])
        did = int(r["district_id_id"])
        code = r.get("code")
        rows.append(
            {
                "id": sid,
                "district_id": did,
                "name": str(r["name"]),
                "code": str(code if code is not None else sid),
            }
        )
        district_ids.add(did)

    if district_ids:
        existing = set(
            op.get_bind()
            .execute(
                sa.text("SELECT id FROM districts WHERE id IN :ids").bindparams(
                    sa.bindparam("ids", expanding=True)
                ),
                {"ids": sorted(district_ids)},
            )
            .scalars()
            .all()
        )
        missing = sorted(district_ids - existing)
        if missing:
            raise RuntimeError(
                "Missing districts required by subdistrict seed. "
                "Ensure `0004_seed_geo_districts` seeded all district rows. "
                f"First missing district ids: {missing[:50]}"
            )

    _upsert_by_id("sub_districts", rows)


def downgrade() -> None:
    seed_path = (
        Path(__file__).resolve().parent.parent
        / "seed_data"
        / "geo"
        / "subdistricts.sql"
    )
    header = seed_path.read_bytes()[:5]
    if header == b"PGDMP":
        raise RuntimeError(
            f"{seed_path} looks like a pg_dump custom-format file (PGDMP). "
            "Please re-export as plain SQL (text) to downgrade seeded data."
        )

    ids: list[int] = []
    src_rows = _read_copy_rows(seed_path, "petition_form_sub_district")
    ids = [int(r["id"]) for r in src_rows if r.get("id") is not None]

    if ids:
        op.execute(
            sa.text("DELETE FROM sub_districts WHERE id IN :ids").bindparams(
                sa.bindparam("ids", expanding=True)
            ),
            {"ids": ids},
        )

