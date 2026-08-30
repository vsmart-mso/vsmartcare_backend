"""Unit tests — Thai fiscal year bounds and Indicators fill/totals helpers."""

from __future__ import annotations

import unittest
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.constants.current_status import (
    CURRENT_STATUS_AID_COMPLETED,
    CURRENT_STATUS_MSO_FORWARDED,
)
from app.services.dwf_scope import SOR_KOR_TYPE_MONEY_ID
from app.services.indicators_summary import (
    DCY_TYPE_MONEY_ID,
    INDICATOR_AIDED_LATEST_STATUS_IDS,
    INDICATOR_FORWARDED_LATEST_STATUS_IDS,
    INDICATOR_TYPE_MONEY_CATEGORY_IDS,
    _build_export_totals,
    _build_items,
    _build_province_items,
    _build_totals,
    _effective_province_id,
    _filter_meta,
    _latest_status_ids_for,
    _map_household_members,
    _nest_regulation_sdshv_rows,
    _normalize_id_list,
    _physical_condition_th,
    _format_money,
    _self_care_th,
    _sor_kor_mother_province_map,
)
from app.schemas.indicators import (
    IndicatorApproverSdshvItem,
    IndicatorCaseStatus,
    IndicatorExportCaseItem,
    IndicatorRegulationBreakdownItem,
)
from app.utils.budget_year import (
    thai_fiscal_year,
    thai_fiscal_year_bounds,
    thai_fiscal_year_bounds_from_be,
)
from app.utils.datetime_th import format_thai_date

_BANGKOK = ZoneInfo("Asia/Bangkok")

# DWF บ้านสองแคว — พิษณุโลก (แม่) / พิจิตร (ลูก)
_PHITSANULOK_MOTHER = 65
_PHICHIT_CHILD = 66
_NON_DWF_PROVINCE = 99  # ไม่มีใน drpod_dwf.json


class TestThaiFiscalYearBoundsFromBe(unittest.TestCase):
    def test_budget_year_2568_bounds(self) -> None:
        start, end = thai_fiscal_year_bounds_from_be(2568)
        self.assertEqual(start, datetime(2024, 10, 1, 0, 0, 0, tzinfo=_BANGKOK))
        self.assertEqual(end, datetime(2025, 9, 30, 23, 59, 59, 999999, tzinfo=_BANGKOK))

    def test_budget_year_2567_and_2569(self) -> None:
        start67, end67 = thai_fiscal_year_bounds_from_be(2567)
        self.assertEqual(start67.year, 2023)
        self.assertEqual(start67.month, 10)
        self.assertEqual(end67.year, 2024)
        self.assertEqual(end67.month, 9)

        start69, end69 = thai_fiscal_year_bounds_from_be(2569)
        self.assertEqual(start69, datetime(2025, 10, 1, 0, 0, 0, tzinfo=_BANGKOK))
        self.assertEqual(end69, datetime(2026, 9, 30, 23, 59, 59, 999999, tzinfo=_BANGKOK))

    def test_boundary_dates_map_to_correct_budget_year(self) -> None:
        cases = [
            (datetime(2024, 9, 30, 23, 59, tzinfo=_BANGKOK), 2567),
            (datetime(2024, 10, 1, 0, 0, tzinfo=_BANGKOK), 2568),
            (datetime(2025, 1, 15, 12, 0, tzinfo=_BANGKOK), 2568),
            (datetime(2025, 9, 30, 23, 59, tzinfo=_BANGKOK), 2568),
            (datetime(2025, 10, 1, 0, 0, tzinfo=_BANGKOK), 2569),
        ]
        for aided_at, expected_year in cases:
            with self.subTest(aided_at=aided_at):
                self.assertEqual(thai_fiscal_year(aided_at), expected_year)
                start, end = thai_fiscal_year_bounds_from_be(expected_year)
                self.assertGreaterEqual(aided_at, start)
                self.assertLessEqual(aided_at, end)

    def test_out_of_budget_year_2568_not_inside_bounds(self) -> None:
        start, end = thai_fiscal_year_bounds_from_be(2568)
        before = datetime(2024, 9, 30, 23, 59, tzinfo=_BANGKOK)
        after = datetime(2025, 10, 1, 0, 0, tzinfo=_BANGKOK)
        self.assertLess(before, start)
        self.assertGreater(after, end)

    def test_bounds_from_be_matches_bounds_from_reference(self) -> None:
        ref = datetime(2025, 3, 1, 12, 0, tzinfo=_BANGKOK)
        self.assertEqual(
            thai_fiscal_year_bounds_from_be(thai_fiscal_year(ref)),
            thai_fiscal_year_bounds(ref),
        )


class TestSorKorMotherProvinceRemap(unittest.TestCase):
    def test_dwf_group_members_map_to_mother(self) -> None:
        mother_map = _sor_kor_mother_province_map()
        self.assertEqual(mother_map[_PHICHIT_CHILD], _PHITSANULOK_MOTHER)
        self.assertEqual(mother_map[_PHITSANULOK_MOTHER], _PHITSANULOK_MOTHER)
        self.assertEqual(mother_map[60], _PHITSANULOK_MOTHER)  # นครสวรรค์

    def test_province_outside_dwf_not_in_map(self) -> None:
        mother_map = _sor_kor_mother_province_map()
        self.assertNotIn(_NON_DWF_PROVINCE, mother_map)

    def test_effective_province_sor_kor_child_to_mother(self) -> None:
        self.assertEqual(
            _effective_province_id(_PHICHIT_CHILD, SOR_KOR_TYPE_MONEY_ID),
            _PHITSANULOK_MOTHER,
        )

    def test_effective_province_sor_kor_mother_stays(self) -> None:
        self.assertEqual(
            _effective_province_id(_PHITSANULOK_MOTHER, SOR_KOR_TYPE_MONEY_ID),
            _PHITSANULOK_MOTHER,
        )

    def test_effective_province_other_type_keeps_child(self) -> None:
        # สป. (1) ที่อยู่ลูก → นับลูก
        self.assertEqual(_effective_province_id(_PHICHIT_CHILD, 1), _PHICHIT_CHILD)

    def test_effective_province_sor_kor_outside_dwf_unchanged(self) -> None:
        self.assertEqual(
            _effective_province_id(_NON_DWF_PROVINCE, SOR_KOR_TYPE_MONEY_ID),
            _NON_DWF_PROVINCE,
        )


class TestIndicatorsNationwideSorKorSmoke(unittest.TestCase):
    """Smoke: left-fill nationwide — เงินสค. อยู่แถวแม่ ไม่โผล่แถวลูก."""

    def test_sor_kor_money_on_mother_row_child_zero_fill(self) -> None:
        provinces = [
            SimpleNamespace(id=_PHITSANULOK_MOTHER, name="พิษณุโลก"),
            SimpleNamespace(id=_PHICHIT_CHILD, name="พิจิตร"),
        ]
        # aggregate หลัง remap: สค. จากที่อยู่ลูกไปอยู่แม่แล้ว
        agg = {_PHITSANULOK_MOTHER: (1, Decimal("5000.00"))}
        items = _build_province_items(provinces, agg)
        by_id = {i.province_id: i for i in items}
        self.assertEqual(by_id[_PHITSANULOK_MOTHER].case_count, 1)
        self.assertEqual(
            by_id[_PHITSANULOK_MOTHER].total_money_amount,
            Decimal("5000.00"),
        )
        self.assertEqual(by_id[_PHICHIT_CHILD].case_count, 0)
        self.assertEqual(by_id[_PHICHIT_CHILD].total_money_amount, Decimal("0"))
        totals = _build_totals(items)
        self.assertEqual(totals.case_count, 1)
        self.assertEqual(totals.total_money_amount, Decimal("5000.00"))


class TestIndicatorsFillAndTotals(unittest.TestCase):
    def _categories(self) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                id=i,
                name=f"cat-{i}",
                name_acronym=f"A{i}",
                name_acrovym_eng=f"e{i}",
            )
            for i in INDICATOR_TYPE_MONEY_CATEGORY_IDS
        ]

    def test_six_types_always_present_even_when_zero(self) -> None:
        items = _build_items(self._categories(), {})
        self.assertEqual(len(items), 6)
        self.assertEqual(
            [i.type_money_category_id for i in items],
            list(INDICATOR_TYPE_MONEY_CATEGORY_IDS),
        )
        self.assertTrue(all(i.case_count == 0 for i in items))
        self.assertTrue(all(i.total_money_amount == Decimal("0") for i in items))
        totals = _build_totals(items)
        self.assertEqual(totals.case_count, 0)
        self.assertEqual(totals.total_money_amount, Decimal("0"))

    def test_totals_sum_partial_agg_and_null_money_as_zero(self) -> None:
        agg = {
            1: (2, Decimal("10000.00")),
            3: (1, Decimal("0")),
        }
        items = _build_items(self._categories(), agg)
        by_id = {i.type_money_category_id: i for i in items}
        self.assertEqual(by_id[1].case_count, 2)
        self.assertEqual(by_id[1].total_money_amount, Decimal("10000.00"))
        self.assertEqual(by_id[3].case_count, 1)
        self.assertEqual(by_id[3].total_money_amount, Decimal("0"))
        self.assertEqual(by_id[2].case_count, 0)
        totals = _build_totals(items)
        self.assertEqual(totals.case_count, 3)
        self.assertEqual(totals.total_money_amount, Decimal("10000.00"))

    def test_filter_meta_status_ids(self) -> None:
        aided = _filter_meta(IndicatorCaseStatus.aided)
        self.assertEqual(aided.case_status, IndicatorCaseStatus.aided)
        self.assertEqual(aided.latest_status_id, CURRENT_STATUS_AID_COMPLETED)
        self.assertEqual(aided.aided_status_id, CURRENT_STATUS_AID_COMPLETED)

        forwarded = _filter_meta(IndicatorCaseStatus.forwarded)
        self.assertEqual(forwarded.case_status, IndicatorCaseStatus.forwarded)
        self.assertEqual(forwarded.latest_status_id, CURRENT_STATUS_MSO_FORWARDED)
        self.assertEqual(forwarded.aided_status_id, 4)

        self.assertEqual(
            _latest_status_ids_for(IndicatorCaseStatus.aided),
            INDICATOR_AIDED_LATEST_STATUS_IDS,
        )
        self.assertEqual(
            INDICATOR_AIDED_LATEST_STATUS_IDS,
            (CURRENT_STATUS_AID_COMPLETED,),
        )
        self.assertEqual(
            _latest_status_ids_for(IndicatorCaseStatus.forwarded),
            INDICATOR_FORWARDED_LATEST_STATUS_IDS,
        )
        self.assertEqual(
            INDICATOR_FORWARDED_LATEST_STATUS_IDS,
            (CURRENT_STATUS_MSO_FORWARDED,),
        )

    def test_uncategorized_type_not_in_items(self) -> None:
        """เคสไม่มี type 1–6 ต้องไม่โผล่ใน items (aggregate กรองก่อน fill)."""
        agg = {7: (5, Decimal("999")), 1: (1, Decimal("100"))}
        items = _build_items(self._categories(), agg)
        ids = {i.type_money_category_id for i in items}
        self.assertEqual(ids, set(INDICATOR_TYPE_MONEY_CATEGORY_IDS))
        self.assertNotIn(7, ids)
        self.assertEqual(_build_totals(items).case_count, 1)

    def test_by_regulation_nested_under_dcy(self) -> None:
        reg = IndicatorRegulationBreakdownItem(
            regulation_id=50,
            regulation_name="ระเบียบเด็ก",
            regulation_short_name="ดย.",
            case_count=3,
            total_money_amount=Decimal("9000.00"),
            by_approver_sdshv=[
                IndicatorApproverSdshvItem(
                    user_sdshv="sw.a",
                    case_count=2,
                    total_money_amount=Decimal("6000.00"),
                ),
                IndicatorApproverSdshvItem(
                    user_sdshv=None,
                    case_count=1,
                    total_money_amount=Decimal("3000.00"),
                ),
            ],
        )
        items = _build_items(
            self._categories(),
            {DCY_TYPE_MONEY_ID: (3, Decimal("9000.00"))},
            {DCY_TYPE_MONEY_ID: [reg]},
        )
        dcy = next(i for i in items if i.type_money_category_id == DCY_TYPE_MONEY_ID)
        self.assertEqual(len(dcy.by_regulation), 1)
        self.assertEqual(dcy.by_regulation[0].regulation_id, 50)
        self.assertEqual(len(dcy.by_regulation[0].by_approver_sdshv), 2)
        spo = next(i for i in items if i.type_money_category_id == 1)
        self.assertEqual(spo.by_regulation, [])


class TestNestRegulationSdshv(unittest.TestCase):
    def test_nest_groups_regulation_and_sdshv(self) -> None:
        rows = [
            SimpleNamespace(
                type_money_category_id=DCY_TYPE_MONEY_ID,
                regulation_id=50,
                regulation_name="reg-a",
                regulation_short_name="A",
                user_sdshv="sw.a",
                case_count=2,
                total_money_amount=Decimal("4000"),
            ),
            SimpleNamespace(
                type_money_category_id=DCY_TYPE_MONEY_ID,
                regulation_id=50,
                regulation_name="reg-a",
                regulation_short_name="A",
                user_sdshv=None,
                case_count=1,
                total_money_amount=Decimal("1000"),
            ),
            SimpleNamespace(
                type_money_category_id=DCY_TYPE_MONEY_ID,
                regulation_id=51,
                regulation_name="reg-b",
                regulation_short_name="B",
                user_sdshv="sw.b",
                case_count=1,
                total_money_amount=Decimal("2000"),
            ),
            SimpleNamespace(
                type_money_category_id=1,
                regulation_id=None,
                regulation_name=None,
                regulation_short_name=None,
                user_sdshv=None,
                case_count=1,
                total_money_amount=Decimal("0"),
            ),
        ]
        nested = _nest_regulation_sdshv_rows(rows)
        self.assertEqual(len(nested[DCY_TYPE_MONEY_ID]), 2)
        reg50 = next(r for r in nested[DCY_TYPE_MONEY_ID] if r.regulation_id == 50)
        self.assertEqual(reg50.case_count, 3)
        self.assertEqual(reg50.total_money_amount, Decimal("5000"))
        self.assertEqual(
            [s.user_sdshv for s in reg50.by_approver_sdshv],
            ["sw.a", None],
        )
        self.assertEqual(nested[1][0].regulation_id, None)
        self.assertEqual(nested[1][0].case_count, 1)


class TestIndicatorsProvinceFill(unittest.TestCase):
    def test_all_provinces_present_even_when_zero(self) -> None:
        provinces = [
            SimpleNamespace(id=10, name="กรุงเทพมหานคร"),
            SimpleNamespace(id=11, name="สมุทรปราการ"),
            SimpleNamespace(id=12, name="นนทบุรี"),
        ]
        items = _build_province_items(provinces, {10: (2, Decimal("15000.00"))})
        self.assertEqual(len(items), 3)
        by_id = {i.province_id: i for i in items}
        self.assertEqual(by_id[10].case_count, 2)
        self.assertEqual(by_id[10].total_money_amount, Decimal("15000.00"))
        self.assertEqual(by_id[11].case_count, 0)
        self.assertEqual(by_id[12].total_money_amount, Decimal("0"))
        totals = _build_totals(items)
        self.assertEqual(totals.case_count, 2)
        self.assertEqual(totals.total_money_amount, Decimal("15000.00"))
        self.assertFalse(any("type_money_category_id" in i.model_dump() for i in items))


class TestIndicatorsExportHelpers(unittest.TestCase):
    def test_normalize_id_list_dedupes_and_preserves_order(self) -> None:
        self.assertIsNone(_normalize_id_list(None))
        self.assertIsNone(_normalize_id_list([]))
        self.assertEqual(_normalize_id_list([6, 1, 6, 2]), [6, 1, 2])

    def test_export_totals_from_items_null_money_as_zero(self) -> None:
        items = [
            IndicatorExportCaseItem(
                applicant_id=1,
                first_name="A",
                last_name="B",
                cid="1234567890123",
                birth_date="1 ม.ค. 2533",
                address_province_id=_PHICHIT_CHILD,
                address_province_name="พิจิตร",
                effective_province_id=_PHITSANULOK_MOTHER,
                effective_province_name="พิษณุโลก",
                money_amount="5,000.00",
            ),
            IndicatorExportCaseItem(
                applicant_id=2,
                first_name="C",
                last_name="D",
                cid="1234567890124",
                birth_date="2 ก.พ. 2534",
                address_province_id=_PHITSANULOK_MOTHER,
                address_province_name="พิษณุโลก",
                effective_province_id=_PHITSANULOK_MOTHER,
                effective_province_name="พิษณุโลก",
                money_amount=None,
            ),
        ]
        totals = _build_export_totals(items)
        self.assertEqual(totals.case_count, 2)
        self.assertEqual(totals.total_money_amount, Decimal("5000.00"))

    def test_export_remap_smoke_child_address_effective_mother(self) -> None:
        """สค. ที่อยู่ลูก → address ยังเป็นลูก แต่ effective เป็นแม่ (เหมือนแถว export)."""
        address_province_id = _PHICHIT_CHILD
        type_money_category_id = SOR_KOR_TYPE_MONEY_ID
        effective = _effective_province_id(address_province_id, type_money_category_id)
        self.assertEqual(effective, _PHITSANULOK_MOTHER)
        item = IndicatorExportCaseItem(
            applicant_id=99,
            first_name="สค",
            last_name="ลูก",
            cid="1234567890199",
            birth_date="5 พ.ค. 2528",
            address_province_id=address_province_id,
            address_province_name="พิจิตร",
            effective_province_id=effective,
            effective_province_name="พิษณุโลก",
            type_money_category_id=type_money_category_id,
            type_money_name_acronym="สค.",
            money_amount="3,000.00",
        )
        self.assertEqual(item.address_province_id, _PHICHIT_CHILD)
        self.assertEqual(item.effective_province_id, _PHITSANULOK_MOTHER)
        totals = _build_export_totals([item])
        self.assertEqual(totals.case_count, 1)
        self.assertEqual(totals.total_money_amount, Decimal("3000.00"))

    def test_export_agency_fields_optional_for_smart_filter(self) -> None:
        item = IndicatorExportCaseItem(
            applicant_id=1,
            first_name="A",
            last_name="B",
            cid="1234567890123",
            birth_date="1 ม.ค. 2533",
            address_province_id=_PHICHIT_CHILD,
            address_province_name="พิจิตร",
            effective_province_id=_PHITSANULOK_MOTHER,
            effective_province_name="พิษณุโลก",
            aided_org_sdshv="sw.diag",
            aided_org_name="พมจ.พิษณุโลก",
            forward_sdshv="sw.forward",
            disburse_sdshv="sw.pay",
            responsible_division_id=65,
        )
        self.assertEqual(item.aided_org_sdshv, "sw.diag")
        self.assertEqual(item.forward_sdshv, "sw.forward")
        self.assertEqual(item.disburse_sdshv, "sw.pay")
        self.assertEqual(item.responsible_division_id, 65)


class TestIndicatorsExportThaiLabels(unittest.TestCase):
    def test_format_thai_date_be_year_and_month_abbr(self) -> None:
        self.assertEqual(format_thai_date(datetime(2026, 2, 5).date()), "5 ก.พ. 2569")
        self.assertEqual(format_thai_date("1990-01-01"), "1 ม.ค. 2533")
        self.assertIsNone(format_thai_date(None))

    def test_format_thai_date_notified_at_uses_bangkok_calendar_day(self) -> None:
        utc_evening = datetime(2026, 2, 4, 20, 0, 0)
        self.assertEqual(format_thai_date(utc_evening), "5 ก.พ. 2569")
        self.assertEqual(format_thai_date(datetime(2026, 2, 5, 1, 0, 0)), "5 ก.พ. 2569")

    def test_physical_condition_and_self_care_thai(self) -> None:
        self.assertEqual(_physical_condition_th("normal"), "ปกติ")
        self.assertEqual(_physical_condition_th("disabled"), "พิการ")
        self.assertEqual(_physical_condition_th("chronic_illness"), "เจ็บป่วยเรื้อรัง")
        self.assertEqual(_self_care_th(True), "ได้")
        self.assertEqual(_self_care_th(False), "ไม่ได้")

    def test_map_household_members_formats_labels(self) -> None:
        mapped = _map_household_members(
            [
                {
                    "seq": 1,
                    "prefix_name": "เด็กชาย",
                    "first_name": "สมชาย",
                    "last_name": "ใจดี",
                    "cid": "1234567890123",
                    "date_of_birth": "2015-03-01",
                    "age": 10,
                    "relation_name": "บุตร",
                    "occupation": "นักเรียน",
                    "monthly_income": "1500.5",
                    "physical_condition": "normal",
                    "self_care": True,
                }
            ]
        )
        self.assertEqual(len(mapped), 1)
        member = mapped[0]
        self.assertEqual(member.cid, "1234567890123")
        self.assertEqual(member.date_of_birth, "1 มี.ค. 2558")
        self.assertEqual(member.monthly_income, "1,500.50")
        self.assertEqual(member.physical_condition, "ปกติ")
        self.assertEqual(member.self_care, "ได้")

    def test_format_money_thousand_separator(self) -> None:
        self.assertEqual(_format_money(Decimal("5000")), "5,000.00")
        self.assertEqual(_format_money("1500.5"), "1,500.50")
        self.assertIsNone(_format_money(None))

    def test_household_member_count_excludes_applicant(self) -> None:
        mapped = _map_household_members(
            [
                {
                    "seq": 1,
                    "first_name": "ก",
                    "last_name": "ข",
                    "cid": "1111111111111",
                    "physical_condition": "normal",
                    "self_care": True,
                },
                {
                    "seq": 2,
                    "first_name": "ค",
                    "last_name": "ง",
                    "cid": "",
                    "physical_condition": "disabled",
                    "self_care": False,
                },
            ]
        )
        self.assertEqual(len(mapped), 2)
        self.assertEqual(mapped[0].cid, "1111111111111")
        self.assertIsNone(mapped[1].cid)


if __name__ == "__main__":
    unittest.main()
