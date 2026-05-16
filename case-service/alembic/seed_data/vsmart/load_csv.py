"""Load VSmart seed CSV files for Alembic migrations."""

from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

_VSMART_DIR = Path(__file__).resolve().parent

_BOOL_COLUMNS = frozenset({"activate", "requires_ktb_form"})
_INT_COLUMNS = frozenset(
    {
        "id",
        "type_money_category_id",
        "limit_per_budget_year",
        "sort_order",
        "vsmart_legacy_id",
    }
)
_DECIMAL_COLUMNS = frozenset({"maximum_money"})


def _coerce(column: str, raw: str) -> object | None:
    if raw == "":
        return None
    if column in _BOOL_COLUMNS:
        return raw.strip().lower() in {"1", "true", "t", "yes"}
    if column in _INT_COLUMNS:
        return int(raw)
    if column in _DECIMAL_COLUMNS:
        return Decimal(raw)
    return raw


def load_vsmart_csv(filename: str) -> list[dict]:
    path = _VSMART_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"VSmart seed CSV not found: {path}")

    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            {key: _coerce(key, value) for key, value in row.items()}
            for row in reader
        ]
