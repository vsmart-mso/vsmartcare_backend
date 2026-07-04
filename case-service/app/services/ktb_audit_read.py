"""อ่านฟิลด์ audit KTB สำหรับ API response (default เคสเก่าก่อน migration)."""

from __future__ import annotations

from typing import Any

from ..constants.attachment_types import ATTACHMENT_TYPE_KTB_CORPORATE
from ..models.applicant import Applicant
from ..models.applicant_submission_audit import ApplicantSubmissionAudit
from ..models.welfare import WelfareEvidence


def _has_ktb_evidence(applicant: Applicant) -> bool:
    for ev in applicant.welfare_evidences or []:
        if ev.attachment_type_id == ATTACHMENT_TYPE_KTB_CORPORATE:
            return True
    return False


def ktb_audit_api_fields(
    applicant: Applicant,
    audit: ApplicantSubmissionAudit | None = None,
) -> dict[str, Any]:
    """Flatten audit → response; เคสไม่มีแถว audit ใช้ default require=true."""
    row = audit if audit is not None else getattr(applicant, "submission_audit", None)

    if row is None:
        fields: dict[str, Any] = {
            "require_ktb_corporate": True,
            "require_ktb_reason": "NEW_CASE",
            "existing_case_source": None,
            "existing_case_detected_sources": None,
            "existing_case_ref_id": None,
            "existing_case_province_id": None,
            "existing_case_province_name": None,
            "submission_province_id": None,
            "submission_province_name": None,
            "is_account_changed": None,
        }
    else:
        fields = {
            "require_ktb_corporate": row.require_ktb_corporate,
            "require_ktb_reason": row.require_ktb_reason,
            "existing_case_source": row.existing_case_source,
            "existing_case_detected_sources": row.existing_case_detected_sources,
            "existing_case_ref_id": row.existing_case_ref_id,
            "existing_case_province_id": row.existing_case_province_id,
            "existing_case_province_name": row.existing_case_province_name,
            "submission_province_id": row.submission_province_id,
            "submission_province_name": row.submission_province_name,
            "is_account_changed": row.is_account_changed,
        }

    has_ktb = _has_ktb_evidence(applicant)
    prior_reuse_id: int | None = None
    if not fields["require_ktb_corporate"]:
        source = fields.get("existing_case_source")
        ref_id = fields.get("existing_case_ref_id")
        if source in ("VCARE", "Legacy") and ref_id is not None:
            prior_reuse_id = int(ref_id)

    fields["has_ktb_evidence"] = has_ktb
    fields["prior_ktb_reuse_applicant_id"] = prior_reuse_id
    return fields


def enrich_case_for_staff_ktb_defaults(data: dict[str, Any]) -> None:
    """เติม default สำหรับ list row ที่ไม่มี audit join."""
    if data.get("require_ktb_corporate") is None:
        data["require_ktb_corporate"] = True
    if not data.get("require_ktb_reason"):
        data["require_ktb_reason"] = "NEW_CASE"
