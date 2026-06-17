"""Unit tests สำหรับ scoped other-text validation ใน case welfare schemas."""

import unittest

from app.schemas.case_welfare import DependencyLoadInCase, EconomicIncomeSourceInCase


class TestScopedOtherTextValidation(unittest.TestCase):
    def test_income_source_other_details_only_on_id_99(self) -> None:
        row = EconomicIncomeSourceInCase(
            income_source_type_id=1,
            other_details="should be cleared",
        )
        self.assertIsNone(row.other_details)

    def test_income_source_other_details_kept_on_id_99(self) -> None:
        row = EconomicIncomeSourceInCase(
            income_source_type_id=99,
            other_details="รายได้จากขายของ",
        )
        self.assertEqual(row.other_details, "รายได้จากขายของ")

    def test_income_source_other_details_trimmed_on_id_99(self) -> None:
        row = EconomicIncomeSourceInCase(
            income_source_type_id=99,
            other_details="  ทดสอบ  ",
        )
        self.assertEqual(row.other_details, "ทดสอบ")

    def test_income_source_blank_other_becomes_none_on_id_99(self) -> None:
        row = EconomicIncomeSourceInCase(
            income_source_type_id=99,
            other_details="   ",
        )
        self.assertIsNone(row.other_details)

    def test_dependency_other_text_only_on_id_99(self) -> None:
        row = DependencyLoadInCase(
            dependency_type_id=2,
            dependency_other_text="should be cleared",
        )
        self.assertIsNone(row.dependency_other_text)

    def test_dependency_other_text_kept_on_id_99(self) -> None:
        row = DependencyLoadInCase(
            dependency_type_id=99,
            dependency_other_text="ดูแลผู้ป่วยเรื้อรัง",
        )
        self.assertEqual(row.dependency_other_text, "ดูแลผู้ป่วยเรื้อรัง")


if __name__ == "__main__":
    unittest.main()
