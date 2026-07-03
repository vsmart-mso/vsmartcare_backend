"""VSMART legacy path compatibility — rewrite citizen routes to staff when X-API-Key."""

from __future__ import annotations

from typing import Any

from .middleware import merge_forward_headers


def vsmart_internal_headers() -> dict[str, str]:
    """Headers for case-service staff routes (inject STAFF_INTERNAL_API_KEY)."""
    return merge_forward_headers(inject_internal_api_key=True)


def staff_evidence_url(
    base: str,
    applicant_id: int,
    evidence_id: int | None = None,
    *,
    file: bool = False,
) -> str:
    """Build case-service staff evidence URL from applicant/evidence ids."""
    root = base.rstrip("/")
    if evidence_id is None:
        return f"{root}/v1/case_for_staff/applicant/{applicant_id}/evidences"
    if file:
        return (
            f"{root}/v1/case_for_staff/applicant/{applicant_id}/evidences/{evidence_id}/file"
        )
    return f"{root}/v1/case_for_staff/applicant/{applicant_id}/evidences/{evidence_id}"


def case_compat_from_por_kor_1(detail: dict[str, Any], applicant_id: int) -> dict[str, Any]:
    """Slim GET /v1/cases/{id} shape for VSMART Print ปสค.1."""
    members: list[dict[str, Any]] = []
    for member in detail.get("household_members") or []:
        item = dict(member)
        item.pop("member_evidences", None)
        members.append(item)
    return {
        "applicant_id": applicant_id,
        "household_members": members,
    }
