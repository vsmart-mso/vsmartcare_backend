"""Unit tests — VCARE check-case prior_case + submission_audit parity."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from app.models.applicant_submission_audit import ApplicantSubmissionAudit
from app.services.ktb_requirement import (
    attach_submission_audit_to_detail,
    compute_ktb_requirement,
    finalize_detail_submission_audit,
    fetch_vcare_prior_case_detail,
    prior_ref_from_vcare_case,
    ProvinceRef,
    submission_audit_snapshot_from_vcare_prior,
)


class TestVcareSubmissionAuditSnapshot(unittest.TestCase):
    def test_snapshot_from_vcare_prior(self) -> None:
        prior = {
            "ref_id": 42,
            "applicant_id": 42,
            "province_id": 10,
            "province_name": "นครราชสีมา",
            "bank_account_no": "1234567890",
        }
        snap = submission_audit_snapshot_from_vcare_prior(prior)
        self.assertEqual(snap["existing_case_source"], "VCARE")
        self.assertEqual(snap["existing_case_ref_id"], 42)
        self.assertEqual(snap["existing_case_province_id"], 10)
        self.assertEqual(snap["existing_case_province_name"], "นครราชสีมา")
        self.assertEqual(snap["submission_province_id"], 10)
        self.assertEqual(snap["submission_province_name"], "นครราชสีมา")
        self.assertIsNone(snap["is_account_changed"])
        self.assertIsNone(snap["require_ktb_corporate"])
        self.assertIsNone(snap["require_ktb_reason"])

    def test_attach_vcare_synthetic(self) -> None:
        prior = {"ref_id": 1, "province_id": 5, "province_name": "กรุงเทพมหานคร"}
        detail: dict = {}
        attach_submission_audit_to_detail(detail, prior, source_label="VCARE")
        self.assertTrue(detail["has_submission_audit"])
        self.assertEqual(detail["submission_audit"]["existing_case_source"], "VCARE")

    def test_finalize_uses_db_row_when_present(self) -> None:
        audit = ApplicantSubmissionAudit(
            applicant_id=7,
            existing_case_source="VCARE",
            existing_case_ref_id=7,
            existing_case_province_id=20,
            existing_case_province_name="ชลบุรี",
            submission_province_id=10,
            submission_province_name="กรุงเทพมหานคร",
            is_account_changed=False,
            require_ktb_corporate=False,
            require_ktb_reason="NONE",
        )
        prior = {"ref_id": 7, "province_id": 20, "province_name": "ชลบุรี"}
        detail: dict = {}
        finalize_detail_submission_audit(
            detail, prior, source_label="VCARE", audit_row=audit,
        )
        self.assertTrue(detail["has_submission_audit"])
        self.assertEqual(detail["submission_audit"]["existing_case_province_id"], 20)
        self.assertEqual(detail["submission_audit"]["require_ktb_reason"], "NONE")

    def test_finalize_synthetic_when_no_audit_row(self) -> None:
        prior = {"ref_id": 3, "province_id": 1, "province_name": "เชียงใหม่"}
        detail: dict = {}
        finalize_detail_submission_audit(detail, prior, source_label="VCARE")
        self.assertEqual(detail["submission_audit"]["existing_case_source"], "VCARE")
        self.assertIsNone(detail["submission_audit"]["require_ktb_reason"])


class TestComputeKtbRequirement(unittest.TestCase):
    def test_none_prior_with_submission_province_triggers_province_changed(self) -> None:
        """Regression: refresh ที่ตัดเคสปัจจุบันแล้วไม่หา prior ใหม่ → require ผิด."""
        result = compute_ktb_requirement(
            is_existing_case=True,
            prior=None,
            submission=ProvinceRef(65, "พิษณุโลก"),
            submission_bank_account_no="8570826060",
        )
        self.assertTrue(result["require_ktb_corporate"])
        self.assertEqual(result["require_ktb_reason"], "PROVINCE_CHANGED")

    def test_same_province_and_account_does_not_require(self) -> None:
        prior = prior_ref_from_vcare_case({
            "ref_id": 13,
            "province_id": 65,
            "province_name": "พิษณุโลก",
            "bank_account_no": "8570826060",
        })
        result = compute_ktb_requirement(
            is_existing_case=True,
            prior=prior,
            submission=ProvinceRef(65, "พิษณุโลก"),
            submission_bank_account_no="8570826060",
        )
        self.assertFalse(result["require_ktb_corporate"])
        self.assertEqual(result["require_ktb_reason"], "NONE")
        self.assertEqual(result["existing_case_ref_id"], 13)


class TestFetchVcarePriorCaseDetail(unittest.IsolatedAsyncioTestCase):
    async def test_prior_uses_existing_case_province_from_audit(self) -> None:
        audit = MagicMock(spec=ApplicantSubmissionAudit)
        audit.existing_case_province_id = 99
        audit.existing_case_province_name = "อุบลราชธานี"
        audit.submission_province_id = 10
        audit.submission_province_name = "กรุงเทพมหานคร"

        applicant = MagicMock()
        applicant.id = 55
        applicant.bank_account_no = "9876543210"
        applicant.submission_audit = audit
        applicant.addresses = []

        session = AsyncMock()
        session.scalar = AsyncMock(return_value=applicant)

        result = await fetch_vcare_prior_case_detail(session, person_id=1)
        assert result is not None
        prior_case, audit_row = result
        self.assertEqual(prior_case["province_id"], 99)
        self.assertEqual(prior_case["province_name"], "อุบลราชธานี")
        self.assertEqual(prior_case["bank_account_no"], "9876543210")
        self.assertIs(audit_row, audit)

    async def test_prior_fallback_address_when_no_audit(self) -> None:
        province = MagicMock()
        province.id = 30
        province.name = "ขอนแก่น"

        district = MagicMock()
        district.province = province

        sub_district = MagicMock()
        sub_district.district = district

        sdp = MagicMock()
        sdp.sub_district = sub_district

        addr = MagicMock()
        addr.address_type = None
        addr.sub_district_postcode = sdp

        applicant = MagicMock()
        applicant.id = 12
        applicant.bank_account_no = "111"
        applicant.submission_audit = None
        applicant.addresses = [addr]

        session = AsyncMock()
        session.scalar = AsyncMock(return_value=applicant)

        result = await fetch_vcare_prior_case_detail(session, person_id=2)
        assert result is not None
        prior_case, audit_row = result
        self.assertEqual(prior_case["province_id"], 30)
        self.assertEqual(prior_case["province_name"], "ขอนแก่น")
        self.assertIsNone(audit_row)

    async def test_returns_none_when_no_applicant(self) -> None:
        session = AsyncMock()
        session.scalar = AsyncMock(return_value=None)
        result = await fetch_vcare_prior_case_detail(session, person_id=999)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
