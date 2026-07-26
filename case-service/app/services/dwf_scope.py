"""DWF province-group helpers for Sor Kor case visibility."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
from typing import Any


SOR_KOR_TYPE_MONEY_ID = 6


@dataclass(frozen=True)
class DwfGroup:
    division_id: int
    division_name: str
    mother_province_id: int
    province_ids: tuple[int, ...]


def _candidate_paths() -> tuple[Path, ...]:
    here = Path(__file__).resolve()
    return (
        here.parents[3] / "drpod_dwf.json",
        here.parents[1] / "drpod_dwf.json",
    )


def _load_raw() -> list[dict[str, Any]]:
    for path in _candidate_paths():
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    raise FileNotFoundError("drpod_dwf.json not found")


@lru_cache(maxsize=1)
def dwf_groups() -> tuple[DwfGroup, ...]:
    groups: list[DwfGroup] = []
    for item in _load_raw():
        province_ids = tuple(int(p["code"]) for p in item.get("province", []))
        groups.append(
            DwfGroup(
                division_id=int(item["id"]),
                division_name=str(item["name"]),
                mother_province_id=int(item["default_province"]),
                province_ids=province_ids,
            )
        )
    return tuple(groups)


@lru_cache(maxsize=1)
def _group_by_province() -> dict[int, DwfGroup]:
    mapping: dict[int, DwfGroup] = {}
    for group in dwf_groups():
        for province_id in group.province_ids:
            mapping[province_id] = group
    return mapping


@lru_cache(maxsize=1)
def _division_names() -> dict[int, str]:
    return {group.division_id: group.division_name for group in dwf_groups()}


def group_for_province(province_id: int) -> DwfGroup | None:
    return _group_by_province().get(province_id)


def division_name_for_id(division_id: int | None) -> str | None:
    if division_id is None:
        return None
    return _division_names().get(division_id)


def is_dwf_mother_province(province_id: int) -> bool:
    group = group_for_province(province_id)
    return group is not None and group.mother_province_id == province_id


def allowed_sor_kor_province_ids(province_id: int) -> tuple[int, ...]:
    group = group_for_province(province_id)
    if group is None:
        return (province_id,)
    if group.mother_province_id == province_id:
        return group.province_ids
    return (province_id,)


def visible_cover_document_batch_province_ids(
    province_id: int,
    type_money_id: int | None,
) -> tuple[int, ...]:
    # Cover-document batches still allow DWF mother provinces to manage Sor Kor child-province cases.
    if type_money_id == SOR_KOR_TYPE_MONEY_ID:
        return allowed_sor_kor_province_ids(province_id)
    return (province_id,)


def visible_finance_sor_kor_province_ids(province_id: int) -> tuple[int, ...]:
    # Finance is stricter than the main list: child provinces must not see Sor Kor finance rows.
    group = group_for_province(province_id)
    if group is None:
        return (province_id,)
    if group.mother_province_id == province_id:
        return group.province_ids
    return ()
