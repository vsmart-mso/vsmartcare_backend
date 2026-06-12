"""หาหมายเลขคำร้อง self-submit อื่นในปีงบเดียวกัน — สำหรับ staff list."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.applicant import Applicant
from ..utils.budget_year import thai_fiscal_year

SELF_REQUESTER_RELATION_ID = 1


@dataclass(frozen=True)
class _SelfSubmitApplicant:
    applicant_id: int
    persons_id: int
    created_at: datetime
    case_number: str


@dataclass(frozen=True)
class FiscalYearSelfSubmitEnrichment:
    prior_case_numbers: dict[int, list[str]]
    fiscal_year_count: dict[int, int]
    fiscal_year_case_numbers: dict[int, list[str]]


def _row_get(row: Mapping[str, object], key: str) -> object | None:
    return row.get(key)


def _as_int(value: object | None) -> int | None:
    if value is None:
        return None
    return int(value)  # type: ignore[arg-type]


def _prior_numbers_for_group(
    members: list[_SelfSubmitApplicant],
) -> dict[int, list[str]]:
    if len(members) < 2:
        return {}

    latest = max(members, key=lambda m: (m.created_at, m.applicant_id))
    priors = sorted(
        (m for m in members if m.applicant_id != latest.applicant_id),
        key=lambda m: (m.created_at, m.applicant_id),
    )
    return {latest.applicant_id: [m.case_number for m in priors]}


def compute_fiscal_year_self_submit_enrichment(
    all_applicants: Sequence[_SelfSubmitApplicant],
) -> FiscalYearSelfSubmitEnrichment:
    """จัดกลุ่มตาม (persons_id, fiscal_year) — prior numbers ที่แถวล่าสุด, count ทุกแถวในกลุ่ม."""
    groups: dict[tuple[int, int], list[_SelfSubmitApplicant]] = defaultdict(list)
    for applicant in all_applicants:
        fy = thai_fiscal_year(applicant.created_at)
        groups[(applicant.persons_id, fy)].append(applicant)

    prior: dict[int, list[str]] = {}
    fiscal_year_count: dict[int, int] = {}
    fiscal_year_case_numbers: dict[int, list[str]] = {}
    for members in groups.values():
        if len(members) < 2:
            continue
        count = len(members)
        sorted_members = sorted(members, key=lambda m: (m.created_at, m.applicant_id))
        all_case_numbers = [m.case_number for m in sorted_members]
        for member in members:
            fiscal_year_count[member.applicant_id] = count
            fiscal_year_case_numbers[member.applicant_id] = all_case_numbers
        prior.update(_prior_numbers_for_group(members))
    return FiscalYearSelfSubmitEnrichment(
        prior_case_numbers=prior,
        fiscal_year_count=fiscal_year_count,
        fiscal_year_case_numbers=fiscal_year_case_numbers,
    )


def compute_prior_self_submit_case_numbers(
    all_applicants: Sequence[_SelfSubmitApplicant],
) -> dict[int, list[str]]:
    return compute_fiscal_year_self_submit_enrichment(all_applicants).prior_case_numbers


async def _load_self_submit_applicants(
    session: AsyncSession,
    rows: Sequence[Mapping[str, object]],
) -> list[_SelfSubmitApplicant]:
    persons_ids: set[int] = set()
    for row in rows:
        if _as_int(_row_get(row, "requester_relation_id")) != SELF_REQUESTER_RELATION_ID:
            continue
        persons_id = _as_int(_row_get(row, "persons_id"))
        if persons_id is not None:
            persons_ids.add(persons_id)

    if not persons_ids:
        return []

    stmt = (
        select(
            Applicant.id,
            Applicant.persons_id,
            Applicant.created_at,
            Applicant.case_number,
        )
        .where(
            Applicant.persons_id.in_(persons_ids),
            Applicant.requester_relation_id == SELF_REQUESTER_RELATION_ID,
            Applicant.case_number.is_not(None),
        )
        .order_by(Applicant.created_at.asc(), Applicant.id.asc())
    )
    result = await session.execute(stmt)
    return [
        _SelfSubmitApplicant(
            applicant_id=row.id,
            persons_id=row.persons_id,
            created_at=row.created_at,
            case_number=row.case_number,  # type: ignore[arg-type]
        )
        for row in result.all()
        if row.case_number
    ]


async def load_fiscal_year_self_submit_enrichment(
    session: AsyncSession,
    rows: Sequence[Mapping[str, object]],
) -> FiscalYearSelfSubmitEnrichment:
    applicants = await _load_self_submit_applicants(session, rows)
    if not applicants:
        return FiscalYearSelfSubmitEnrichment(
            prior_case_numbers={},
            fiscal_year_count={},
            fiscal_year_case_numbers={},
        )
    return compute_fiscal_year_self_submit_enrichment(applicants)


async def load_prior_self_submit_case_numbers(
    session: AsyncSession,
    rows: Sequence[Mapping[str, object]],
) -> dict[int, list[str]]:
    enrichment = await load_fiscal_year_self_submit_enrichment(session, rows)
    return enrichment.prior_case_numbers
