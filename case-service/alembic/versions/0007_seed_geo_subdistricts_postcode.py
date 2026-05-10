"""seed master geo data (sub_districts_postcode bridge)

Revision ID: 0007_seed_sd_pc
Revises: 0006_seed_geo_postcodes
Create Date: 2026-05-09 00:00:00.000000

Source: `subdistrict.sql` dump (subdistrict_id + zipcode).
"""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = "0007_seed_sd_pc"
down_revision: str | Sequence[str] | None = "0006_seed_geo_postcodes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UQ_NAME = "uq_sub_districts_postcode_subdistrict_postcode"


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
    # Add uniqueness so we can seed idempotently without relying on surrogate `id`.
    op.create_unique_constraint(
        UQ_NAME, "sub_districts_postcode", ["sub_district_id", "postcode_id"]
    )

    seed_path = (
        Path(__file__).resolve().parent.parent
        / "seed_data"
        / "geo"
        / "postcode.sql"
    )
    header = seed_path.read_bytes()[:5]
    if header == b"PGDMP":
        raise RuntimeError(
            f"{seed_path} looks like a pg_dump custom-format file (PGDMP). "
            "Please re-export as plain SQL (text) with INSERT/COPY statements."
        )

    src_rows = _read_copy_rows(seed_path, "petition_form_postcode")
    rows: list[dict] = []
    seen: set[tuple[int, int]] = set()
    for r in src_rows:
        if r.get("sub_district_id_id") is None or r.get("postcode") is None:
            continue
        subdistrict_id = int(r["sub_district_id_id"])
        postcode_str = str(r["postcode"]).strip()
        if not postcode_str:
            continue
        postcode_id = int(postcode_str)
        key = (subdistrict_id, postcode_id)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"sub_district_id": subdistrict_id, "postcode_id": postcode_id})

    if rows:
        op.get_bind().execute(
            sa.text(
                "INSERT INTO sub_districts_postcode (sub_district_id, postcode_id) "
                "VALUES (:sub_district_id, :postcode_id) "
                "ON CONFLICT (sub_district_id, postcode_id) DO NOTHING"
            ),
            rows,
        )


def downgrade() -> None:
    seed_path = (
        Path(__file__).resolve().parent.parent
        / "seed_data"
        / "geo"
        / "postcode.sql"
    )
    header = seed_path.read_bytes()[:5]
    if header == b"PGDMP":
        raise RuntimeError(
            f"{seed_path} looks like a pg_dump custom-format file (PGDMP). "
            "Please re-export as plain SQL (text) to downgrade seeded data."
        )

    src_rows = _read_copy_rows(seed_path, "petition_form_postcode")
    rows: list[dict] = []
    seen: set[tuple[int, int]] = set()
    for r in src_rows:
        if r.get("sub_district_id_id") is None or r.get("postcode") is None:
            continue
        subdistrict_id = int(r["sub_district_id_id"])
        postcode_str = str(r["postcode"]).strip()
        if not postcode_str:
            continue
        postcode_id = int(postcode_str)
        key = (subdistrict_id, postcode_id)
        if key in seen:
            continue
        seen.add(key)
        rows.append({"sub_district_id": subdistrict_id, "postcode_id": postcode_id})

    if rows:
        op.get_bind().execute(
            sa.text(
                "DELETE FROM sub_districts_postcode "
                "WHERE sub_district_id = :sub_district_id AND postcode_id = :postcode_id"
            ),
            rows,
        )

    op.drop_constraint(UQ_NAME, "sub_districts_postcode", type_="unique")

