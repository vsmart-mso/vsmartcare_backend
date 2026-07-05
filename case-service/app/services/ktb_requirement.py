"""คำนวณ Require KTB Corporate Online ตอนยื่นคำร้อง + แปลงแหล่งตรวจรายเดิม."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.applicant import Applicant
from ..models.applicant_submission_audit import ApplicantSubmissionAudit
from ..models.address import Address
from ..models.geo import District, Province, SubDistrict, SubDistrictPostcode
from ..models.lookup import AddressType
from ..schemas.case_welfare import AddressInCase
from ..schemas.check_case import CheckCaseSource, ExistingCaseCheckResult

KtbRequireReason = Literal["NEW_CASE", "NONE", "ACCOUNT_CHANGED", "PROVINCE_CHANGED"]

_SOURCE_LABEL: dict[CheckCaseSource, str] = {
    "vcare_main": "VCARE",
    "vsmart_main": "Legacy",
    "mso_logbook": "Welfare",
}


@dataclass(frozen=True)
class ProvinceRef:
    province_id: int | None
    province_name: str | None


@dataclass(frozen=True)
class PriorCaseRef:
    source: str
    ref_id: int | None
    province_id: int | None
    province_name: str | None
    bank_account_no: str | None


def normalize_account_no(raw: str | None) -> str:
    if not raw:
        return ""
    return re.sub(r"[\s\-]", "", str(raw).strip())


def normalize_province_name(name: str | None) -> str:
    if not name:
        return ""
    text = str(name).strip().lower()
    text = text.replace("จังหวัด", "").strip()
    return re.sub(r"\s+", "", text)


def pick_prior_case(
    vcare: PriorCaseRef | None,
    legacy: PriorCaseRef | None,
    welfare: PriorCaseRef | None,
) -> PriorCaseRef | None:
    """ลำดับ VCARE → Legacy → Welfare — แหล่งแรกที่มี province_id."""
    for ref in (vcare, legacy, welfare):
        if ref is not None and ref.province_id is not None:
            return ref
    for ref in (vcare, legacy, welfare):
        if ref is not None:
            return ref
    return None


def compute_ktb_requirement(
    *,
    is_existing_case: bool,
    prior: PriorCaseRef | None,
    submission: ProvinceRef,
    submission_bank_account_no: str | None,
) -> dict[str, Any]:
    """คืน dict สำหรับ ApplicantSubmissionAudit + ฟิลด์ audit."""
    base: dict[str, Any] = {
        "existing_case_source": prior.source if prior else None,
        "existing_case_ref_id": prior.ref_id if prior else None,
        "existing_case_province_id": prior.province_id if prior else None,
        "existing_case_province_name": prior.province_name if prior else None,
        "submission_province_id": submission.province_id,
        "submission_province_name": submission.province_name,
    }

    if not is_existing_case:
        return {
            **base,
            "is_account_changed": None,
            "require_ktb_corporate": True,
            "require_ktb_reason": "NEW_CASE",
        }

    prior_province_id = prior.province_id if prior else None
    submission_province_id = submission.province_id
    province_changed = prior_province_id != submission_province_id
    if prior_province_id is None or submission_province_id is None:
        province_changed = prior_province_id != submission_province_id

    prior_account = normalize_account_no(prior.bank_account_no if prior else None)
    submission_account = normalize_account_no(submission_bank_account_no)
    account_changed = prior_account != submission_account

    if province_changed:
        return {
            **base,
            "is_account_changed": account_changed,
            "require_ktb_corporate": True,
            "require_ktb_reason": "PROVINCE_CHANGED",
        }

    if account_changed:
        return {
            **base,
            "is_account_changed": True,
            "require_ktb_corporate": True,
            "require_ktb_reason": "ACCOUNT_CHANGED",
        }

    return {
        **base,
        "is_account_changed": False,
        "require_ktb_corporate": False,
        "require_ktb_reason": "NONE",
    }


def _prior_from_detail(source: CheckCaseSource, detail: dict[str, Any] | None) -> PriorCaseRef | None:
    if not detail:
        return None
    prior = detail.get("prior_case")
    if not isinstance(prior, dict):
        return None
    province_id = prior.get("province_id")
    if province_id is not None:
        try:
            province_id = int(province_id)
        except (TypeError, ValueError):
            province_id = None
    ref_id = prior.get("ref_id", prior.get("informer_id", prior.get("applicant_id")))
    if ref_id is not None:
        try:
            ref_id = int(ref_id)
        except (TypeError, ValueError):
            ref_id = None
    return PriorCaseRef(
        source=_SOURCE_LABEL[source],
        ref_id=ref_id,
        province_id=province_id,
        province_name=prior.get("province_name"),
        bank_account_no=prior.get("bank_account_no"),
    )


def extract_existing_case_detected_sources(
    check: ExistingCaseCheckResult,
) -> list[str] | None:
    if not check.is_existing_case:
        return None
    return [
        src.source for src in check.sources
        if src.available and src.found
    ]


def extract_prior_cases_from_check(
    check: ExistingCaseCheckResult,
) -> tuple[PriorCaseRef | None, PriorCaseRef | None, PriorCaseRef | None]:
    vcare = legacy = welfare = None
    for src in check.sources:
        if not src.found or not src.available:
            continue
        # MSO logbook ใช้แค่ OR is_existing_case — ไม่มี snapshot audit
        if src.source == "mso_logbook":
            continue
        prior = _prior_from_detail(src.source, src.detail)
        if src.source == "vcare_main":
            vcare = prior
        elif src.source == "vsmart_main":
            legacy = prior
    return vcare, legacy, welfare


def submission_audit_snapshot_from_row(audit: ApplicantSubmissionAudit) -> dict[str, Any]:
    """คืน dict ฟิลด์เดียวกับตาราง applicant_submission_audit."""
    return {
        "existing_case_source": audit.existing_case_source,
        "existing_case_detected_sources": audit.existing_case_detected_sources,
        "existing_case_ref_id": audit.existing_case_ref_id,
        "existing_case_province_id": audit.existing_case_province_id,
        "existing_case_province_name": audit.existing_case_province_name,
        "submission_province_id": audit.submission_province_id,
        "submission_province_name": audit.submission_province_name,
        "is_account_changed": audit.is_account_changed,
        "require_ktb_corporate": audit.require_ktb_corporate,
        "require_ktb_reason": audit.require_ktb_reason,
    }


def submission_audit_snapshot_from_legacy_prior(prior: dict[str, Any]) -> dict[str, Any]:
    """Map Legacy prior_case → ฟิลด์เดียวกับ applicant_submission_audit."""
    ref_id = prior.get("ref_id", prior.get("informer_id", prior.get("applicant_id")))
    province_id = prior.get("province_id")
    province_name = prior.get("province_name")
    return {
        "existing_case_source": "Legacy",
        "existing_case_ref_id": ref_id,
        "existing_case_province_id": province_id,
        "existing_case_province_name": province_name,
        "submission_province_id": province_id,
        "submission_province_name": province_name,
        "is_account_changed": None,
        "require_ktb_corporate": None,
        "require_ktb_reason": None,
    }


def submission_audit_snapshot_from_vcare_prior(prior: dict[str, Any]) -> dict[str, Any]:
    """Map VCARE prior_case → ฟิลด์เดียวกับ applicant_submission_audit (สังเคราะห์)."""
    ref_id = prior.get("ref_id", prior.get("applicant_id"))
    province_id = prior.get("province_id")
    province_name = prior.get("province_name")
    return {
        "existing_case_source": "VCARE",
        "existing_case_ref_id": ref_id,
        "existing_case_province_id": province_id,
        "existing_case_province_name": province_name,
        "submission_province_id": province_id,
        "submission_province_name": province_name,
        "is_account_changed": None,
        "require_ktb_corporate": None,
        "require_ktb_reason": None,
    }


def attach_submission_audit_to_detail(
    detail: dict[str, Any],
    prior: dict[str, Any],
    *,
    source_label: str,
) -> None:
    if source_label == "Legacy":
        detail["submission_audit"] = submission_audit_snapshot_from_legacy_prior(prior)
    elif source_label == "VCARE":
        detail["submission_audit"] = submission_audit_snapshot_from_vcare_prior(prior)
    detail["has_submission_audit"] = True


def finalize_detail_submission_audit(
    detail: dict[str, Any],
    prior: dict[str, Any],
    *,
    source_label: str,
    audit_row: ApplicantSubmissionAudit | None = None,
) -> None:
    """ใส่ submission_audit ใน detail — จากแถว DB หรือสังเคราะห์จาก prior_case."""
    if audit_row is not None:
        detail["submission_audit"] = submission_audit_snapshot_from_row(audit_row)
        detail["has_submission_audit"] = True
    else:
        attach_submission_audit_to_detail(detail, prior, source_label=source_label)


async def resolve_province_by_name(
    session: AsyncSession,
    province_name: str | None,
) -> ProvinceRef:
    if not province_name or not str(province_name).strip():
        return ProvinceRef(None, None)
    normalized = normalize_province_name(province_name)
    rows = await session.scalars(select(Province))
    for prov in rows:
        if normalize_province_name(prov.name) == normalized:
            return ProvinceRef(prov.id, prov.name)
    return ProvinceRef(None, province_name.strip())


async def resolve_vcare_province_id(
    session: AsyncSession,
    prior: PriorCaseRef,
) -> PriorCaseRef:
    """แมป province_id จาก Legacy/Welfare → VCARE ด้วยชื่อเมื่อจำเป็น."""
    if prior.province_id is not None:
        prov = await session.get(Province, prior.province_id)
        if prov is not None:
            return prior
    if prior.province_name:
        resolved = await resolve_province_by_name(session, prior.province_name)
        if resolved.province_id is not None:
            return PriorCaseRef(
                source=prior.source,
                ref_id=prior.ref_id,
                province_id=resolved.province_id,
                province_name=resolved.province_name,
                bank_account_no=prior.bank_account_no,
            )
    return prior


async def resolve_submission_province_from_case_addresses(
    session: AsyncSession,
    addresses: list[AddressInCase],
) -> ProvinceRef:
    if not addresses:
        return ProvinceRef(None, None)

    type_ids = {a.address_type_id for a in addresses}
    type_rows = await session.scalars(
        select(AddressType).where(AddressType.id.in_(type_ids))
    )
    type_names = {t.id: (t.name or "") for t in type_rows}

    chosen: AddressInCase | None = None
    for addr in addresses:
        if "ปัจจุบัน" in type_names.get(addr.address_type_id, ""):
            chosen = addr
            break
    if chosen is None:
        chosen = next((a for a in addresses if a.sub_district_postcode_id), None)
    if chosen is None:
        return ProvinceRef(None, None)

    sdp = await session.scalar(
        select(SubDistrictPostcode)
        .where(SubDistrictPostcode.id == chosen.sub_district_postcode_id)
        .options(
            selectinload(SubDistrictPostcode.sub_district)
            .selectinload(SubDistrict.district)
            .selectinload(District.province),
        )
    )
    if sdp is None or sdp.sub_district is None or sdp.sub_district.district is None:
        return ProvinceRef(None, None)
    prov = sdp.sub_district.district.province
    if prov is None:
        return ProvinceRef(None, None)
    return ProvinceRef(prov.id, prov.name)


def resolve_submission_province_from_address_rows(
    addresses: list[Address],
) -> ProvinceRef:
    """ใช้กับ ORM addresses ที่ load geo แล้ว."""
    if not addresses:
        return ProvinceRef(None, None)

    chosen: Address | None = None
    for addr in addresses:
        name = addr.address_type.name if addr.address_type else ""
        if "ปัจจุบัน" in (name or ""):
            chosen = addr
            break
    if chosen is None:
        chosen = addresses[0]

    sdp = chosen.sub_district_postcode
    if sdp is None or sdp.sub_district is None or sdp.sub_district.district is None:
        return ProvinceRef(None, None)
    prov = sdp.sub_district.district.province
    if prov is None:
        return ProvinceRef(None, None)
    return ProvinceRef(prov.id, prov.name)


async def build_submission_audit_fields(
    session: AsyncSession,
    *,
    existing_check: ExistingCaseCheckResult,
    addresses: list[AddressInCase],
    bank_account_no: str | None,
    current_applicant_id: int | None = None,
) -> dict[str, Any]:
    submission = await resolve_submission_province_from_case_addresses(session, addresses)
    vcare, legacy, welfare = extract_prior_cases_from_check(existing_check)

    if (
        current_applicant_id is not None
        and vcare is not None
        and vcare.ref_id == current_applicant_id
    ):
        vcare = None

    if legacy is not None:
        legacy = await resolve_vcare_province_id(session, legacy)
    if welfare is not None:
        welfare = await resolve_vcare_province_id(session, welfare)

    prior = pick_prior_case(vcare, legacy, welfare)
    fields = compute_ktb_requirement(
        is_existing_case=existing_check.is_existing_case,
        prior=prior,
        submission=submission,
        submission_bank_account_no=bank_account_no,
    )
    fields["existing_case_detected_sources"] = extract_existing_case_detected_sources(
        existing_check,
    )
    return fields


async def refresh_applicant_submission_audit(
    session: AsyncSession,
    applicant: Applicant,
    *,
    bank_account_no: str | None,
) -> dict[str, Any]:
    """คำนวณ audit ใหม่จากเลขบัญชีล่าสุด (เช่น หลังบันทึกหน้า 13)."""
    from ..api.check_case import check_existing_case_by_cid

    person = applicant.person
    if person is None or not person.cid:
        return {}

    existing_check = await check_existing_case_by_cid(session, person.cid)
    submission = resolve_submission_province_from_address_rows(list(applicant.addresses or []))
    vcare, legacy, welfare = extract_prior_cases_from_check(existing_check)

    if vcare is not None and vcare.ref_id == applicant.id:
        vcare = None

    # check_existing_case_by_cid คืนเคสล่าสุดของ CID (มักเป็นเคสปัจจุบัน) — หาเคสอ้างอิงจริง
    if vcare is None and person.id is not None:
        fallback = await fetch_vcare_prior_case_detail(
            session,
            person.id,
            exclude_applicant_id=applicant.id,
        )
        if fallback is not None:
            prior_case, _audit = fallback
            vcare = prior_ref_from_vcare_case(prior_case)

    if legacy is not None:
        legacy = await resolve_vcare_province_id(session, legacy)
    if welfare is not None:
        welfare = await resolve_vcare_province_id(session, welfare)

    prior = pick_prior_case(vcare, legacy, welfare)
    fields = compute_ktb_requirement(
        is_existing_case=existing_check.is_existing_case,
        prior=prior,
        submission=submission,
        submission_bank_account_no=bank_account_no,
    )
    fields["existing_case_detected_sources"] = extract_existing_case_detected_sources(
        existing_check,
    )

    audit = applicant.submission_audit
    if audit is None:
        session.add(ApplicantSubmissionAudit(applicant_id=applicant.id, **fields))
    else:
        for key, value in fields.items():
            setattr(audit, key, value)
        audit.computed_at = datetime.utcnow()

    return fields


async def load_applicant_for_audit_refresh(
    session: AsyncSession,
    applicant_id: int,
) -> Applicant | None:
    stmt = (
        select(Applicant)
        .where(Applicant.id == applicant_id)
        .options(
            selectinload(Applicant.person),
            selectinload(Applicant.submission_audit),
            selectinload(Applicant.addresses).selectinload(Address.address_type),
            selectinload(Applicant.addresses)
            .selectinload(Address.sub_district_postcode)
            .selectinload(SubDistrictPostcode.sub_district)
            .selectinload(SubDistrict.district)
            .selectinload(District.province),
        )
    )
    return await session.scalar(stmt)


def prior_ref_from_vcare_case(prior_case: dict[str, Any]) -> PriorCaseRef:
    ref_id = prior_case.get("ref_id", prior_case.get("applicant_id"))
    if ref_id is not None:
        try:
            ref_id = int(ref_id)
        except (TypeError, ValueError):
            ref_id = None
    province_id = prior_case.get("province_id")
    if province_id is not None:
        try:
            province_id = int(province_id)
        except (TypeError, ValueError):
            province_id = None
    return PriorCaseRef(
        source="VCARE",
        ref_id=ref_id,
        province_id=province_id,
        province_name=prior_case.get("province_name"),
        bank_account_no=prior_case.get("bank_account_no"),
    )


async def fetch_vcare_prior_case_detail(
    session: AsyncSession,
    person_id: int,
    *,
    exclude_applicant_id: int | None = None,
) -> tuple[dict[str, Any], ApplicantSubmissionAudit | None] | None:
    """ข้อมูล prior_case จากเคส VCARE ล่าสุด (คู่กับ audit row ถ้ามี).

    ``exclude_applicant_id`` — ข้ามเคสปัจจุบันเมื่อ refresh audit หลังบันทึกหน้า 13
    เพื่อให้ได้เคสอ้างอิงจริง (เช่น รายเดิม #13) แทนเคสที่กำลังยื่น (#14).

    คืน ``(prior_case, audit_row)`` — ไม่ใส่ ``submission_audit`` ใน dict;
    ให้ ``finalize_detail_submission_audit`` จัดการแทน
    """
    stmt = select(Applicant).where(Applicant.persons_id == person_id)
    if exclude_applicant_id is not None:
        stmt = stmt.where(Applicant.id != exclude_applicant_id)
    stmt = (
        stmt.order_by(Applicant.id.desc())
        .limit(1)
        .options(
            selectinload(Applicant.submission_audit),
            selectinload(Applicant.addresses).selectinload(Address.address_type),
            selectinload(Applicant.addresses)
            .selectinload(Address.sub_district_postcode)
            .selectinload(SubDistrictPostcode.sub_district)
            .selectinload(SubDistrict.district)
            .selectinload(District.province),
        )
    )
    applicant = await session.scalar(stmt)
    if applicant is None:
        return None

    audit = applicant.submission_audit
    if audit is not None:
        province_id = audit.existing_case_province_id or audit.submission_province_id
        province_name = audit.existing_case_province_name or audit.submission_province_name
    else:
        province = resolve_submission_province_from_address_rows(list(applicant.addresses))
        province_id = province.province_id
        province_name = province.province_name

    prior_case = {
        "applicant_id": applicant.id,
        "ref_id": applicant.id,
        "province_id": province_id,
        "province_name": province_name,
        "bank_account_no": applicant.bank_account_no,
    }
    return prior_case, audit
