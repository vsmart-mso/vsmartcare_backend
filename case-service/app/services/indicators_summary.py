"""สรุปตัวชี้วัดเงินช่วยเหลือ พม Care 6 ประเภท (รายจังหวัด / รวมทั้งประเทศ)."""

from __future__ import annotations

import json
from decimal import Decimal
from functools import lru_cache

from sqlalchemy import Integer, and_, case, func, literal, or_, select
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from ..constants.current_status import (
    CURRENT_STATUS_AID_COMPLETED,
    CURRENT_STATUS_MSO_FORWARDED,
    CURRENT_STATUS_PENDING_INTAKE,
    CURRENT_STATUS_WITHDRAWING,
)
from ..constants.staff_digest import CURRENT_STATUS_WITHDRAWING_IDS
from ..constants.type_send import TYPE_SEND_MINISTRY
from ..models.address import Address
from ..models.applicant import Applicant
from ..models.applicant_submission_audit import ApplicantSubmissionAudit
from ..models.dependency import DependencyLoad
from ..models.diagnosis import CaseDiagnosis
from ..models.economic import EconomicIncomeSource, EconomicInfo, HouseholdMember
from ..models.geo import District, Postcode, Province, SubDistrict, SubDistrictPostcode
from ..models.intake import (
    AnnouncementRegulation,
    CaseHandling,
    CasePayment,
    CaseRegulationChoice,
    PaymentMethod,
)
from ..models.lookup import (
    BankName,
    DependencyType,
    HouseholdMemberRelationType,
    HousingType,
    IncomeSourceType,
    MaritalStatusType,
    OccupationType,
    PrefixType,
    ReceivedWelfareType,
    RequestType,
    RequesterRelationType,
    TypeMoney,
    TypeMoneyCategory,
)
from ..models.mso_send import SendData
from ..models.payment import ApproveCase, WelfarePayment
from ..models.person import Person
from ..models.status_log import WelfareRequestStatus
from ..models.welfare import WelfareHistory, WelfareHistoryDetail, WelfareRequestType
from ..schemas.indicators import (
    IndicatorApproverSdshvItem,
    IndicatorCaseStatus,
    IndicatorExportCaseItem,
    IndicatorExportFilterMeta,
    IndicatorExportHouseholdMemberItem,
    IndicatorFilterMeta,
    IndicatorMoneyItem,
    IndicatorNationwideFilterMeta,
    IndicatorProvinceItem,
    IndicatorProvinceOverviewFilterMeta,
    IndicatorProvinceOverviewItem,
    IndicatorProvinceOverviewTotals,
    IndicatorRegulationBreakdownItem,
    IndicatorTotals,
    IndicatorsByProvinceResponse,
    IndicatorsExportResponse,
    IndicatorsNationwideResponse,
    IndicatorsProvinceOverviewResponse,
)
from ..utils.budget_year import thai_fiscal_year_bounds_from_be
from ..utils.datetime_th import format_thai_date
from .dwf_scope import SOR_KOR_TYPE_MONEY_ID, division_name_for_id, dwf_groups

INDICATOR_TYPE_MONEY_CATEGORY_IDS: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
# ดย. / DCY — เงินสงเคราะห์เด็กในครอบครัวยากจน
DCY_TYPE_MONEY_ID = 2
PHYSICAL_CONDITION_TH: dict[str, str] = {
    "normal": "ปกติ",
    "disabled": "พิการ",
    "chronic_illness": "เจ็บป่วยเรื้อรัง",
}
EXPORT_CASE_CHANNEL = "พม.CARE"
EXPORT_AGG_SEP = "; "

# case_status=aided — ช่วยเหลือแล้วเท่านั้น (4)
INDICATOR_AIDED_LATEST_STATUS_IDS: tuple[int, ...] = (
    CURRENT_STATUS_AID_COMPLETED,
)
# case_status=forwarded — ส่งต่อกระทรวงแล้ว
INDICATOR_FORWARDED_LATEST_STATUS_IDS: tuple[int, ...] = (
    CURRENT_STATUS_MSO_FORWARDED,
)

# province-overview buckets (snapshot สถานะปัจจุบัน — ไม่ผูกปีงบ ยกเว้นยอดเงิน)
OVERVIEW_PENDING_STATUS_ID: int = CURRENT_STATUS_PENDING_INTAKE  # 1 รอรับเรื่อง
OVERVIEW_DISBURSEMENT_STATUS_IDS: tuple[int, ...] = CURRENT_STATUS_WITHDRAWING_IDS  # 3,10
OVERVIEW_AIDED_STATUS_IDS: tuple[int, ...] = (
    CURRENT_STATUS_WITHDRAWING,  # 10
    CURRENT_STATUS_AID_COMPLETED,  # 4
    CURRENT_STATUS_MSO_FORWARDED,  # 11
)
# ยอดเงินใช้ _latest_status_ids_for(case_status) — aided→4 / forwarded→11


@lru_cache(maxsize=1)
def _sor_kor_mother_province_map() -> dict[int, int]:
    """ทุก province ในกลุ่ม DWF ชี้ไป mother_province_id (รวมตัวแม่เอง)."""
    mapping: dict[int, int] = {}
    for group in dwf_groups():
        for province_id in group.province_ids:
            mapping[province_id] = group.mother_province_id
    return mapping


def _effective_province_id(
    address_province_id: int,
    type_money_category_id: int | None,
) -> int:
    """Python mirror ของ SQL remap — สค. ในกลุ่ม DWF นับที่จังหวัดแม่."""
    if type_money_category_id == SOR_KOR_TYPE_MONEY_ID:
        return _sor_kor_mother_province_map().get(
            address_province_id,
            address_province_id,
        )
    return address_province_id


def _effective_province_id_expr(
    address_province_col: ColumnElement,
    type_money_col: ColumnElement,
) -> ColumnElement:
    """SQL CASE: สค. (type 6) + จังหวัดใน DWF map → mother; นอกนั้นใช้ที่อยู่เดิม."""
    mother_map = _sor_kor_mother_province_map()
    if not mother_map:
        return address_province_col

    remapped = case(
        *[
            (address_province_col == child_id, mother_id)
            for child_id, mother_id in mother_map.items()
        ],
        else_=address_province_col,
    )
    return case(
        (type_money_col == SOR_KOR_TYPE_MONEY_ID, remapped),
        else_=address_province_col,
    )


def _aided_at_subquery():
    return (
        select(
            WelfareRequestStatus.applicant_id.label("applicant_id"),
            func.min(WelfareRequestStatus.created_at).label("aided_at"),
        )
        .where(WelfareRequestStatus.current_status_id == CURRENT_STATUS_AID_COMPLETED)
        .group_by(WelfareRequestStatus.applicant_id)
        .subquery()
    )


def _latest_welfare_request_status_subquery():
    return (
        select(
            WelfareRequestStatus.applicant_id.label("applicant_id"),
            WelfareRequestStatus.current_status_id.label("current_status_id"),
            func.row_number()
            .over(
                partition_by=WelfareRequestStatus.applicant_id,
                order_by=[
                    WelfareRequestStatus.updated_at.desc(),
                    WelfareRequestStatus.id.desc(),
                ],
            )
            .label("rn"),
        )
        .subquery()
    )


def _province_applicants_base(province_ids: list[int] | None):
    """Applicant + จังหวัดที่อยู่ + effective_province (สค. remap ไปแม่ตาม DWF)."""
    primary_address_sq = (
        select(
            Address.applicant_id.label("applicant_id"),
            Address.sub_district_postcode_id.label("sub_district_postcode_id"),
            func.row_number()
            .over(
                partition_by=Address.applicant_id,
                order_by=[Address.id.asc()],
            )
            .label("rn"),
        )
        .subquery()
    )

    location_subdistrict_postcode_id = func.coalesce(
        primary_address_sq.c.sub_district_postcode_id,
        Person.sub_district_postcode_id,
    )
    address_province_col = Province.id
    effective_province_col = _effective_province_id_expr(
        address_province_col,
        Applicant.type_money_category_id,
    )

    stmt = (
        select(
            Applicant.id.label("applicant_id"),
            address_province_col.label("address_province_id"),
            effective_province_col.label("effective_province_id"),
        )
        .select_from(Applicant)
        .join(Person, Person.id == Applicant.persons_id)
        .outerjoin(
            primary_address_sq,
            and_(
                primary_address_sq.c.applicant_id == Applicant.id,
                primary_address_sq.c.rn == 1,
            ),
        )
        .join(
            SubDistrictPostcode,
            SubDistrictPostcode.id == location_subdistrict_postcode_id,
        )
        .join(Postcode, Postcode.id == SubDistrictPostcode.postcode_id)
        .join(SubDistrict, SubDistrict.id == SubDistrictPostcode.sub_district_id)
        .join(District, District.id == SubDistrict.district_id)
        .join(Province, Province.id == District.province_id)
    )
    if province_ids is not None:
        stmt = stmt.where(effective_province_col.in_(province_ids))
    return stmt.subquery()


def _latest_status_ids_for(case_status: IndicatorCaseStatus) -> tuple[int, ...]:
    if case_status == IndicatorCaseStatus.forwarded:
        return INDICATOR_FORWARDED_LATEST_STATUS_IDS
    return INDICATOR_AIDED_LATEST_STATUS_IDS


def _filter_meta(case_status: IndicatorCaseStatus) -> IndicatorFilterMeta:
    if case_status == IndicatorCaseStatus.forwarded:
        latest_status_id = CURRENT_STATUS_MSO_FORWARDED
    else:
        latest_status_id = CURRENT_STATUS_AID_COMPLETED
    return IndicatorFilterMeta(
        case_status=case_status,
        latest_status_id=latest_status_id,
        aided_status_id=CURRENT_STATUS_AID_COMPLETED,
    )


def _build_items(
    categories: list[TypeMoneyCategory],
    agg_by_id: dict[int, tuple[int, Decimal]],
    regulation_by_type: dict[int, list[IndicatorRegulationBreakdownItem]] | None = None,
) -> list[IndicatorMoneyItem]:
    items: list[IndicatorMoneyItem] = []
    for cat in categories:
        case_count, total_money = agg_by_id.get(cat.id, (0, Decimal("0")))
        items.append(
            IndicatorMoneyItem(
                type_money_category_id=cat.id,
                name=cat.name,
                name_acronym=cat.name_acronym,
                name_acrovym_eng=cat.name_acrovym_eng,
                case_count=case_count,
                total_money_amount=total_money,
                by_regulation=(regulation_by_type or {}).get(cat.id, []),
            )
        )
    return items


def _latest_approved_user_sdshv_subquery():
    """แถว approve_case ล่าสุดที่อนุมัติสำเร็จ ต่อ applicant → user_sdshv."""
    return (
        select(
            ApproveCase.applicant_id.label("applicant_id"),
            ApproveCase.user_sdshv.label("user_sdshv"),
            func.row_number()
            .over(
                partition_by=ApproveCase.applicant_id,
                order_by=[ApproveCase.id.desc()],
            )
            .label("rn"),
        )
        .where(ApproveCase.approve_status.is_(True))
        .subquery()
    )


def _nest_regulation_sdshv_rows(
    rows: list,
) -> dict[int, list[IndicatorRegulationBreakdownItem]]:
    """จัดแถว GROUP BY type/regulation/approver → nested by_regulation[].by_approver_sdshv[]."""
    type_map: dict[
        int,
        dict[
            tuple[int | None, str | None, str | None],
            list[tuple[str | None, int, Decimal]],
        ],
    ] = {}

    for row in rows:
        type_id = int(row.type_money_category_id)
        reg_key = (
            int(row.regulation_id) if row.regulation_id is not None else None,
            row.regulation_name,
            row.regulation_short_name,
        )
        sdshv = row.user_sdshv
        case_count = int(row.case_count)
        total_money = _to_decimal(row.total_money_amount)
        type_map.setdefault(type_id, {}).setdefault(reg_key, []).append(
            (sdshv, case_count, total_money)
        )

    result: dict[int, list[IndicatorRegulationBreakdownItem]] = {}
    for type_id, regs in type_map.items():
        reg_items: list[IndicatorRegulationBreakdownItem] = []
        for (reg_id, reg_name, reg_short), sdshv_rows in regs.items():
            sdshv_items = [
                IndicatorApproverSdshvItem(
                    user_sdshv=sdshv,
                    case_count=cnt,
                    total_money_amount=money,
                )
                for sdshv, cnt, money in sdshv_rows
            ]
            sdshv_items.sort(
                key=lambda i: (i.user_sdshv is None, i.user_sdshv or "")
            )
            reg_items.append(
                IndicatorRegulationBreakdownItem(
                    regulation_id=reg_id,
                    regulation_name=reg_name,
                    regulation_short_name=reg_short,
                    case_count=sum(i.case_count for i in sdshv_items),
                    total_money_amount=sum(
                        (i.total_money_amount for i in sdshv_items),
                        start=Decimal("0"),
                    ),
                    by_approver_sdshv=sdshv_items,
                )
            )
        reg_items.sort(
            key=lambda i: (
                i.regulation_id is None,
                i.regulation_id or 0,
                i.regulation_short_name or "",
            )
        )
        result[type_id] = reg_items
    return result


def _build_totals(
    items: list[IndicatorMoneyItem] | list[IndicatorProvinceItem],
) -> IndicatorTotals:
    return IndicatorTotals(
        case_count=sum(i.case_count for i in items),
        total_money_amount=sum(
            (i.total_money_amount for i in items),
            start=Decimal("0"),
        ),
    )


def _build_province_items(
    provinces: list,
    agg_by_id: dict[int, tuple[int, Decimal]],
) -> list[IndicatorProvinceItem]:
    items: list[IndicatorProvinceItem] = []
    for province in provinces:
        case_count, total_money = agg_by_id.get(province.id, (0, Decimal("0")))
        items.append(
            IndicatorProvinceItem(
                province_id=province.id,
                province_name=province.name,
                case_count=case_count,
                total_money_amount=total_money,
            )
        )
    return items


def _to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _parse_export_money(value: object | None) -> Decimal:
    """แปลงจำนวนเงินในแถว export (Decimal หรือข้อความมี comma) เป็น Decimal สำหรับบวกยอด."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    raw = str(value).replace(",", "").strip()
    if not raw:
        return Decimal("0")
    return Decimal(raw)


def _format_money(value: object | None) -> str | None:
    """จำนวนเงินสำหรับ Excel เช่น 5,000.00 — null ถ้าว่าง."""
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    amount = _parse_export_money(value)
    return f"{amount:,.2f}"


def _physical_condition_th(value: object) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    return PHYSICAL_CONDITION_TH.get(raw, raw)


def _self_care_th(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("ได้", "ไม่ได้"):
            return value.strip()
        if lowered in ("true", "1", "yes"):
            return "ได้"
        if lowered in ("false", "0", "no"):
            return "ไม่ได้"
    return "ได้" if value else "ไม่ได้"


def _household_member_cid(value: object) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    return raw or None


def _blank_to_none(value: object) -> str | None:
    return _household_member_cid(value)


def _fiscal_naive_bounds(budget_year: int) -> tuple:
    fiscal_start, fiscal_end = thai_fiscal_year_bounds_from_be(budget_year)
    # DB columns (esp. welfare_request_status.created_at) are timestamp without time zone;
    # compare with Asia/Bangkok wall-clock as naive to avoid aware/naive mix in asyncpg.
    return fiscal_start.replace(tzinfo=None), fiscal_end.replace(tzinfo=None)


def _normalize_id_list(ids: list[int] | None) -> list[int] | None:
    if not ids:
        return None
    return list(dict.fromkeys(ids))


def _apply_eligible_filters(
    stmt,
    province_sq,
    budget_year: int,
    *,
    case_status: IndicatorCaseStatus = IndicatorCaseStatus.aided,
    aided_at_sq=None,
):
    fiscal_start_naive, fiscal_end_naive = _fiscal_naive_bounds(budget_year)
    if aided_at_sq is None:
        aided_at_sq = _aided_at_subquery()
    latest_status_sq = _latest_welfare_request_status_subquery()
    effective_aided_at = func.coalesce(
        aided_at_sq.c.aided_at,
        Applicant.process_completed_at,
    )
    latest_status_ids = _latest_status_ids_for(case_status)
    return (
        stmt.select_from(Applicant)
        .join(province_sq, province_sq.c.applicant_id == Applicant.id)
        .join(
            latest_status_sq,
            and_(
                latest_status_sq.c.applicant_id == Applicant.id,
                latest_status_sq.c.rn == 1,
                latest_status_sq.c.current_status_id.in_(latest_status_ids),
            ),
        )
        .outerjoin(aided_at_sq, aided_at_sq.c.applicant_id == Applicant.id)
        .outerjoin(CaseHandling, CaseHandling.applicant_id == Applicant.id)
        .outerjoin(
            CaseRegulationChoice,
            CaseRegulationChoice.case_handling_id == CaseHandling.id,
        )
        .where(
            Applicant.type_money_category_id.in_(INDICATOR_TYPE_MONEY_CATEGORY_IDS),
            effective_aided_at.is_not(None),
            effective_aided_at.between(fiscal_start_naive, fiscal_end_naive),
        )
    )


def _export_address_detail_subquery():
    return (
        select(
            Address.applicant_id.label("applicant_id"),
            Address.house_number.label("house_number"),
            Address.house_moo.label("house_moo"),
            Address.alley.label("alley"),
            Address.road.label("road"),
            Address.latitude.label("latitude"),
            Address.longitude.label("longitude"),
            Address.sub_district_postcode_id.label("sub_district_postcode_id"),
            func.row_number()
            .over(
                partition_by=Address.applicant_id,
                order_by=[Address.id.asc()],
            )
            .label("rn"),
        )
        .subquery()
    )


def _export_economic_subquery():
    return (
        select(
            EconomicInfo.applicant_id.label("applicant_id"),
            EconomicInfo.occupation.label("occupation"),
            EconomicInfo.monthly_income.label("monthly_income"),
            EconomicInfo.family_occupation.label("family_occupation"),
            EconomicInfo.housing_shelter.label("housing_shelter"),
            EconomicInfo.housing_types_rent.label("housing_rent"),
            EconomicInfo.housing_types_id.label("housing_types_id"),
            func.row_number()
            .over(
                partition_by=EconomicInfo.applicant_id,
                order_by=[EconomicInfo.id.asc()],
            )
            .label("rn"),
        )
        .subquery()
    )


def _sql_label_with_other(name_col: ColumnElement, other_col: ColumnElement):
    """ชื่อ lookup + (other) เมื่อมีข้อความอื่น."""
    return case(
        (
            and_(other_col.is_not(None), other_col != ""),
            func.concat(name_col, " (", other_col, ")"),
        ),
        else_=name_col,
    )


def _latest_diagnosis_subquery():
    """แถว case_diagnosis ล่าสุดต่อ applicant (id DESC)."""
    return (
        select(
            CaseDiagnosis.applicant_id.label("applicant_id"),
            CaseDiagnosis.diagnosis_text.label("diagnosis_text"),
            CaseDiagnosis.owner_name.label("owner_name"),
            CaseDiagnosis.owner_position.label("owner_position"),
            CaseDiagnosis.owner_sdshv.label("owner_sdshv"),
            CaseDiagnosis.owner_organization.label("owner_organization"),
            func.row_number()
            .over(
                partition_by=CaseDiagnosis.applicant_id,
                order_by=[CaseDiagnosis.id.desc()],
            )
            .label("rn"),
        )
        .subquery()
    )


def _latest_forward_send_subquery():
    """แถว send_data ส่งต่อกระทรวงล่าสุดต่อ applicant → send_by_sdshv."""
    return (
        select(
            SendData.applicant_id.label("applicant_id"),
            SendData.send_by_sdshv.label("send_by_sdshv"),
            func.row_number()
            .over(
                partition_by=SendData.applicant_id,
                order_by=[SendData.id.desc()],
            )
            .label("rn"),
        )
        .where(SendData.type_send_id == TYPE_SEND_MINISTRY)
        .subquery()
    )


def _latest_disburse_payment_subquery():
    """แถว welfare_payment ล่าสุดต่อ applicant → user_sdshv ผู้เบิกจ่าย."""
    return (
        select(
            WelfarePayment.applicant_id.label("applicant_id"),
            WelfarePayment.user_sdshv.label("user_sdshv"),
            func.row_number()
            .over(
                partition_by=WelfarePayment.applicant_id,
                order_by=[WelfarePayment.id.desc()],
            )
            .label("rn"),
        )
        .subquery()
    )


def _export_income_sources_agg_subquery():
    label = _sql_label_with_other(
        IncomeSourceType.name,
        EconomicIncomeSource.other_details,
    )
    return (
        select(
            EconomicInfo.applicant_id.label("applicant_id"),
            # PG: string_agg(expr, delim ORDER BY …) — order attaches to delimiter arg
            func.string_agg(
                label,
                aggregate_order_by(literal(EXPORT_AGG_SEP), IncomeSourceType.id.asc()),
            ).label("income_source_names"),
        )
        .select_from(EconomicIncomeSource)
        .join(EconomicInfo, EconomicInfo.id == EconomicIncomeSource.economic_id)
        .join(
            IncomeSourceType,
            IncomeSourceType.id == EconomicIncomeSource.income_source_type_id,
        )
        .group_by(EconomicInfo.applicant_id)
        .subquery()
    )


def _export_dependency_agg_subquery():
    label = _sql_label_with_other(
        DependencyType.name,
        DependencyLoad.dependency_other_text,
    )
    return (
        select(
            DependencyLoad.applicant_id.label("applicant_id"),
            func.string_agg(
                label,
                aggregate_order_by(literal(EXPORT_AGG_SEP), DependencyType.id.asc()),
            ).label("dependency_summary"),
        )
        .select_from(DependencyLoad)
        .join(
            DependencyType,
            DependencyType.id == DependencyLoad.dependency_type_id,
        )
        .group_by(DependencyLoad.applicant_id)
        .subquery()
    )


def _export_household_members_agg_subquery():
    """สมาชิกครัวเรือนเป็น json_agg — ไม่รวมแถวที่เป็นผู้ประสบปัญหา (match cid หรือชื่อ-นามสกุล)."""
    age_years = case(
        (
            HouseholdMember.date_of_birth.is_not(None),
            func.cast(
                func.date_part("year", func.age(HouseholdMember.date_of_birth)),
                Integer,
            ),
        ),
        else_=None,
    )
    prefix_name = func.coalesce(
        func.nullif(HouseholdMember.prefix_other, ""),
        PrefixType.name,
    )
    occupation_name = func.coalesce(
        HouseholdMember.occupation,
        OccupationType.name,
    )
    member_obj = func.json_build_object(
        "seq",
        HouseholdMember.seq,
        "prefix_name",
        prefix_name,
        "first_name",
        HouseholdMember.first_name,
        "last_name",
        HouseholdMember.last_name,
        "cid",
        HouseholdMember.national_id,
        "date_of_birth",
        HouseholdMember.date_of_birth,
        "age",
        age_years,
        "relation_name",
        HouseholdMemberRelationType.name,
        "occupation",
        occupation_name,
        "monthly_income",
        HouseholdMember.monthly_income,
        "physical_condition",
        HouseholdMember.physical_condition,
        "self_care",
        HouseholdMember.self_care,
    )
    is_applicant_person = or_(
        and_(
            HouseholdMember.national_id.is_not(None),
            HouseholdMember.national_id != "",
            HouseholdMember.national_id == Person.cid,
        ),
        and_(
            HouseholdMember.first_name == Person.first_name,
            HouseholdMember.last_name == Person.last_name,
        ),
    )
    return (
        select(
            HouseholdMember.applicant_id.label("applicant_id"),
            func.json_agg(
                aggregate_order_by(member_obj, HouseholdMember.seq.asc()),
            ).label("household_members"),
        )
        .select_from(HouseholdMember)
        .join(Applicant, Applicant.id == HouseholdMember.applicant_id)
        .join(Person, Person.id == Applicant.persons_id)
        .outerjoin(
            PrefixType,
            PrefixType.id == HouseholdMember.prefix_id,
        )
        .outerjoin(
            HouseholdMemberRelationType,
            HouseholdMemberRelationType.id
            == HouseholdMember.relation_to_applicant_id,
        )
        .outerjoin(
            OccupationType,
            OccupationType.id == HouseholdMember.occupation_type_id,
        )
        .where(~is_applicant_person)
        .group_by(HouseholdMember.applicant_id)
        .subquery()
    )


def _map_household_members(raw: object) -> list[IndicatorExportHouseholdMemberItem]:
    """parse json_agg → list[IndicatorExportHouseholdMemberItem]; ว่าง/null → []."""
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = json.loads(raw)
    if not isinstance(raw, list) or not raw:
        return []

    items: list[IndicatorExportHouseholdMemberItem] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        monthly_raw = entry.get("monthly_income")
        age_raw = entry.get("age")
        items.append(
            IndicatorExportHouseholdMemberItem(
                seq=int(entry["seq"]),
                prefix_name=entry.get("prefix_name"),
                first_name=entry["first_name"],
                last_name=entry["last_name"],
                cid=_household_member_cid(entry.get("cid")),
                date_of_birth=format_thai_date(entry.get("date_of_birth")),
                age=int(age_raw) if age_raw is not None else None,
                relation_name=entry.get("relation_name"),
                occupation=entry.get("occupation"),
                monthly_income=_format_money(monthly_raw),
                physical_condition=_physical_condition_th(
                    entry.get("physical_condition")
                ),
                self_care=_self_care_th(entry.get("self_care")),
            )
        )
    return items


def _export_welfare_type_names_agg_subquery():
    label = _sql_label_with_other(
        ReceivedWelfareType.name,
        WelfareHistoryDetail.received_other,
    )
    return (
        select(
            WelfareHistoryDetail.welfare_history_id.label("applicant_id"),
            func.string_agg(
                label,
                aggregate_order_by(literal(EXPORT_AGG_SEP), ReceivedWelfareType.id.asc()),
            ).label("received_welfare_type_names"),
        )
        .select_from(WelfareHistoryDetail)
        .join(
            ReceivedWelfareType,
            ReceivedWelfareType.id
            == WelfareHistoryDetail.received_welfare_type_id,
        )
        .group_by(WelfareHistoryDetail.welfare_history_id)
        .subquery()
    )


def _export_request_types_agg_subquery():
    return (
        select(
            WelfareRequestType.applicant_id.label("applicant_id"),
            func.string_agg(
                RequestType.name,
                aggregate_order_by(literal(EXPORT_AGG_SEP), RequestType.id.asc()),
            ).label("help_request_summary"),
            func.max(WelfareRequestType.request_in_kind_text).label(
                "request_in_kind_text"
            ),
            func.max(WelfareRequestType.request_other_text).label(
                "request_other_text"
            ),
        )
        .select_from(WelfareRequestType)
        .join(RequestType, RequestType.id == WelfareRequestType.request_type_id)
        .group_by(WelfareRequestType.applicant_id)
        .subquery()
    )


def _label_with_other(name: str | None, other: str | None) -> str | None:
    """รวมชื่อ lookup กับข้อความอื่น — ใช้ใน unit test / Python mapping."""
    base = (name or "").strip()
    extra = (other or "").strip()
    if not base and not extra:
        return None
    if base and extra:
        return f"{base} ({extra})"
    return base or extra


def _join_agg_parts(parts: list[str | None], sep: str = EXPORT_AGG_SEP) -> str | None:
    cleaned = [p.strip() for p in parts if p and str(p).strip()]
    if not cleaned:
        return None
    return sep.join(cleaned)


def _build_address_full(
    *,
    house_number: str | None,
    house_moo: str | None,
    alley: str | None,
    road: str | None,
    sub_district_name: str | None,
    district_name: str | None,
    province_name: str | None,
) -> str | None:
    """รวมชิ้นส่วนที่อยู่เป็นข้อความเดียวสำหรับ Excel."""
    parts: list[str] = []
    if house_number:
        parts.append(str(house_number).strip())
    if house_moo:
        parts.append(f"ม.{str(house_moo).strip()}")
    if alley:
        parts.append(str(alley).strip())
    if road:
        parts.append(f"ถ.{str(road).strip()}")
    if sub_district_name:
        parts.append(f"ต.{str(sub_district_name).strip()}")
    if district_name:
        parts.append(f"อ.{str(district_name).strip()}")
    if province_name:
        parts.append(f"จ.{str(province_name).strip()}")
    return " ".join(parts) if parts else None


def _resolve_export_payee(
    *,
    receive_mode: str | None,
    applicant_first_name: str,
    applicant_last_name: str,
    applicant_cid: str,
    applicant_mobile: str | None,
    payee_first_name: str | None,
    payee_last_name: str | None,
    payee_cid: str | None,
    agent_first_name: str | None,
    agent_last_name: str | None,
    agent_cid: str | None,
) -> tuple[str | None, str | None, str | None]:
    """resolve ผู้รับเงินจาก receive_mode + person aliases → (full_name, cid, mobile)."""
    mode = (receive_mode or "").strip().lower()
    if mode == "agent" and (agent_first_name or agent_last_name or agent_cid):
        full_name = _join_agg_parts(
            [agent_first_name, agent_last_name],
            sep=" ",
        )
        return full_name, agent_cid, None
    if payee_first_name or payee_last_name or payee_cid:
        full_name = _join_agg_parts(
            [payee_first_name, payee_last_name],
            sep=" ",
        )
        return full_name, payee_cid, None
    full_name = _join_agg_parts(
        [applicant_first_name, applicant_last_name],
        sep=" ",
    )
    return full_name, applicant_cid, applicant_mobile


def _build_export_totals(items: list[IndicatorExportCaseItem]) -> IndicatorTotals:
    return IndicatorTotals(
        case_count=len(items),
        total_money_amount=sum(
            (_parse_export_money(i.money_amount) for i in items),
            start=Decimal("0"),
        ),
    )


async def _load_type_money_categories(session: AsyncSession) -> list[TypeMoneyCategory]:
    result = await session.execute(
        select(TypeMoneyCategory)
        .where(TypeMoneyCategory.id.in_(INDICATOR_TYPE_MONEY_CATEGORY_IDS))
        .order_by(TypeMoneyCategory.id.asc())
    )
    return list(result.scalars().all())


async def _load_provinces(
    session: AsyncSession,
    province_ids: list[int] | None,
) -> list[Province]:
    stmt = select(Province).order_by(Province.id.asc())
    if province_ids is not None:
        stmt = stmt.where(Province.id.in_(province_ids))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _aggregate_by_type_money(
    session: AsyncSession,
    *,
    budget_year: int,
    province_ids: list[int] | None,
    case_status: IndicatorCaseStatus,
) -> dict[int, tuple[int, Decimal]]:
    province_sq = _province_applicants_base(province_ids)
    stmt = _apply_eligible_filters(
        select(
            Applicant.type_money_category_id.label("type_money_category_id"),
            func.count().label("case_count"),
            func.coalesce(
                func.sum(func.coalesce(CaseRegulationChoice.money_amount, 0)),
                0,
            ).label("total_money_amount"),
        ),
        province_sq,
        budget_year,
        case_status=case_status,
    ).group_by(Applicant.type_money_category_id)

    result = await session.execute(stmt)
    agg: dict[int, tuple[int, Decimal]] = {}
    for row in result.all():
        agg[int(row.type_money_category_id)] = (
            int(row.case_count),
            _to_decimal(row.total_money_amount),
        )
    return agg


async def _aggregate_by_type_regulation_sdshv(
    session: AsyncSession,
    *,
    budget_year: int,
    province_ids: list[int] | None,
    case_status: IndicatorCaseStatus,
) -> dict[int, list[IndicatorRegulationBreakdownItem]]:
    """แยกยอดตามประเภทเงิน → ระเบียบ → approve_case.user_sdshv (ผู้อนุมัติล่าสุดที่อนุมัติ)."""
    province_sq = _province_applicants_base(province_ids)
    approve_sq = _latest_approved_user_sdshv_subquery()
    stmt = _apply_eligible_filters(
        select(
            Applicant.type_money_category_id.label("type_money_category_id"),
            CaseRegulationChoice.regulation_id.label("regulation_id"),
            AnnouncementRegulation.name.label("regulation_name"),
            AnnouncementRegulation.short_name.label("regulation_short_name"),
            approve_sq.c.user_sdshv.label("user_sdshv"),
            func.count().label("case_count"),
            func.coalesce(
                func.sum(func.coalesce(CaseRegulationChoice.money_amount, 0)),
                0,
            ).label("total_money_amount"),
        ),
        province_sq,
        budget_year,
        case_status=case_status,
    )
    stmt = (
        stmt.outerjoin(
            AnnouncementRegulation,
            AnnouncementRegulation.id == CaseRegulationChoice.regulation_id,
        )
        .outerjoin(
            approve_sq,
            and_(
                approve_sq.c.applicant_id == Applicant.id,
                approve_sq.c.rn == 1,
            ),
        )
        .group_by(
            Applicant.type_money_category_id,
            CaseRegulationChoice.regulation_id,
            AnnouncementRegulation.name,
            AnnouncementRegulation.short_name,
            approve_sq.c.user_sdshv,
        )
        .order_by(
            Applicant.type_money_category_id.asc(),
            CaseRegulationChoice.regulation_id.asc().nulls_last(),
            approve_sq.c.user_sdshv.asc().nulls_last(),
        )
    )
    result = await session.execute(stmt)
    return _nest_regulation_sdshv_rows(list(result.all()))


async def _aggregate_by_province(
    session: AsyncSession,
    *,
    budget_year: int,
    province_ids: list[int] | None,
    case_status: IndicatorCaseStatus,
    type_money_category_ids: list[int] | None = None,
) -> dict[int, tuple[int, Decimal]]:
    province_sq = _province_applicants_base(province_ids)
    normalized_type_ids = _normalize_id_list(type_money_category_ids)
    stmt = _apply_eligible_filters(
        select(
            province_sq.c.effective_province_id.label("province_id"),
            func.count().label("case_count"),
            func.coalesce(
                func.sum(func.coalesce(CaseRegulationChoice.money_amount, 0)),
                0,
            ).label("total_money_amount"),
        ),
        province_sq,
        budget_year,
        case_status=case_status,
    )
    if normalized_type_ids is not None:
        stmt = stmt.where(Applicant.type_money_category_id.in_(normalized_type_ids))
    stmt = stmt.group_by(province_sq.c.effective_province_id)

    result = await session.execute(stmt)
    agg: dict[int, tuple[int, Decimal]] = {}
    for row in result.all():
        agg[int(row.province_id)] = (
            int(row.case_count),
            _to_decimal(row.total_money_amount),
        )
    return agg


async def fetch_indicators_by_province(
    session: AsyncSession,
    province_id: int,
    budget_year: int,
    case_status: IndicatorCaseStatus = IndicatorCaseStatus.aided,
) -> IndicatorsByProvinceResponse | None:
    """คืน None เมื่อไม่พบจังหวัด."""
    province = await session.scalar(select(Province).where(Province.id == province_id))
    if province is None:
        return None

    fiscal_start, fiscal_end = thai_fiscal_year_bounds_from_be(budget_year)
    categories = await _load_type_money_categories(session)
    agg = await _aggregate_by_type_money(
        session,
        budget_year=budget_year,
        province_ids=[province_id],
        case_status=case_status,
    )
    regulation_by_type = await _aggregate_by_type_regulation_sdshv(
        session,
        budget_year=budget_year,
        province_ids=[province_id],
        case_status=case_status,
    )
    items = _build_items(categories, agg, regulation_by_type)
    return IndicatorsByProvinceResponse(
        province_id=province.id,
        province_name=province.name,
        budget_year=budget_year,
        fiscal_start=fiscal_start,
        fiscal_end=fiscal_end,
        filter=_filter_meta(case_status),
        items=items,
        totals=_build_totals(items),
    )


async def fetch_indicators_nationwide(
    session: AsyncSession,
    budget_year: int,
    province_ids: list[int] | None = None,
    type_money_category_ids: list[int] | None = None,
    case_status: IndicatorCaseStatus = IndicatorCaseStatus.aided,
) -> IndicatorsNationwideResponse:
    fiscal_start, fiscal_end = thai_fiscal_year_bounds_from_be(budget_year)
    normalized_ids = _normalize_id_list(province_ids)
    normalized_type_ids = _normalize_id_list(type_money_category_ids)
    provinces = await _load_provinces(session, normalized_ids)
    agg = await _aggregate_by_province(
        session,
        budget_year=budget_year,
        province_ids=normalized_ids,
        case_status=case_status,
        type_money_category_ids=normalized_type_ids,
    )
    items = _build_province_items(provinces, agg)
    filter_meta = _filter_meta(case_status)
    return IndicatorsNationwideResponse(
        budget_year=budget_year,
        province_ids=normalized_ids,
        fiscal_start=fiscal_start,
        fiscal_end=fiscal_end,
        filter=IndicatorNationwideFilterMeta(
            case_status=filter_meta.case_status,
            latest_status_id=filter_meta.latest_status_id,
            aided_status_id=filter_meta.aided_status_id,
            province_ids=normalized_ids,
            type_money_category_ids=normalized_type_ids,
        ),
        items=items,
        totals=_build_totals(items),
    )


def _applicant_is_approved_exists():
    """มีแถว approve_case ที่ approve_status = true — เหมือน staff digest finance_pending."""
    return (
        select(ApproveCase.id)
        .where(
            ApproveCase.applicant_id == Applicant.id,
            ApproveCase.approve_status.is_(True),
        )
        .exists()
    )


def _build_province_overview_items(
    provinces: list,
    agg_by_id: dict[int, tuple[Decimal, int, int, int]],
) -> list[IndicatorProvinceOverviewItem]:
    items: list[IndicatorProvinceOverviewItem] = []
    for province in provinces:
        budget, pending, disbursement, aided = agg_by_id.get(
            province.id,
            (Decimal("0"), 0, 0, 0),
        )
        items.append(
            IndicatorProvinceOverviewItem(
                province_id=province.id,
                province_name=province.name,
                total_budget_amount=budget,
                pending_service_case_count=pending,
                disbursement_case_count=disbursement,
                aided_case_count=aided,
            )
        )
    return items


def _build_province_overview_totals(
    items: list[IndicatorProvinceOverviewItem],
) -> IndicatorProvinceOverviewTotals:
    return IndicatorProvinceOverviewTotals(
        total_budget_amount=sum(
            (i.total_budget_amount for i in items),
            start=Decimal("0"),
        ),
        pending_service_case_count=sum(i.pending_service_case_count for i in items),
        disbursement_case_count=sum(i.disbursement_case_count for i in items),
        aided_case_count=sum(i.aided_case_count for i in items),
    )


async def _aggregate_province_overview(
    session: AsyncSession,
    *,
    budget_year: int,
    province_ids: list[int] | None,
    regulation_ids: list[int] | None,
    case_status: IndicatorCaseStatus,
) -> dict[int, tuple[Decimal, int, int, int]]:
    """GROUP BY effective_province — COUNT buckets (snapshot) + SUM money (ปีงบ + case_status)."""
    fiscal_start_naive, fiscal_end_naive = _fiscal_naive_bounds(budget_year)
    province_sq = _province_applicants_base(province_ids)
    latest_status_sq = _latest_welfare_request_status_subquery()
    aided_at_sq = _aided_at_subquery()
    is_approved = _applicant_is_approved_exists()
    effective_aided_at = func.coalesce(
        aided_at_sq.c.aided_at,
        Applicant.process_completed_at,
    )
    current_status = latest_status_sq.c.current_status_id
    budget_status_ids = _latest_status_ids_for(case_status)

    pending_cond = current_status == OVERVIEW_PENDING_STATUS_ID
    disbursement_cond = and_(
        current_status.in_(OVERVIEW_DISBURSEMENT_STATUS_IDS),
        is_approved,
    )
    aided_cond = current_status.in_(OVERVIEW_AIDED_STATUS_IDS)
    budget_cond = and_(
        current_status.in_(budget_status_ids),
        effective_aided_at.is_not(None),
        effective_aided_at.between(fiscal_start_naive, fiscal_end_naive),
    )

    stmt = (
        select(
            province_sq.c.effective_province_id.label("province_id"),
            func.coalesce(
                func.sum(case((pending_cond, 1), else_=0)),
                0,
            ).label("pending_service_case_count"),
            func.coalesce(
                func.sum(case((disbursement_cond, 1), else_=0)),
                0,
            ).label("disbursement_case_count"),
            func.coalesce(
                func.sum(case((aided_cond, 1), else_=0)),
                0,
            ).label("aided_case_count"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            budget_cond,
                            func.coalesce(CaseRegulationChoice.money_amount, 0),
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("total_budget_amount"),
        )
        .select_from(Applicant)
        .join(province_sq, province_sq.c.applicant_id == Applicant.id)
        .join(
            latest_status_sq,
            and_(
                latest_status_sq.c.applicant_id == Applicant.id,
                latest_status_sq.c.rn == 1,
            ),
        )
        .outerjoin(aided_at_sq, aided_at_sq.c.applicant_id == Applicant.id)
        .outerjoin(CaseHandling, CaseHandling.applicant_id == Applicant.id)
        .outerjoin(
            CaseRegulationChoice,
            CaseRegulationChoice.case_handling_id == CaseHandling.id,
        )
    )
    if regulation_ids is not None:
        stmt = stmt.where(CaseRegulationChoice.regulation_id.in_(regulation_ids))
    stmt = stmt.group_by(province_sq.c.effective_province_id)

    result = await session.execute(stmt)
    agg: dict[int, tuple[Decimal, int, int, int]] = {}
    for row in result.all():
        agg[int(row.province_id)] = (
            _to_decimal(row.total_budget_amount),
            int(row.pending_service_case_count),
            int(row.disbursement_case_count),
            int(row.aided_case_count),
        )
    return agg


async def fetch_indicators_province_overview(
    session: AsyncSession,
    budget_year: int,
    province_ids: list[int] | None = None,
    regulation_ids: list[int] | None = None,
    case_status: IndicatorCaseStatus = IndicatorCaseStatus.aided,
) -> IndicatorsProvinceOverviewResponse:
    """สรุป 4 ตัวเลขรายจังหวัด — นับเคสเป็น snapshot; ยอดเงินผูกปีงบ + case_status."""
    fiscal_start, fiscal_end = thai_fiscal_year_bounds_from_be(budget_year)
    normalized_province_ids = _normalize_id_list(province_ids)
    normalized_regulation_ids = _normalize_id_list(regulation_ids)
    provinces = await _load_provinces(session, normalized_province_ids)
    agg = await _aggregate_province_overview(
        session,
        budget_year=budget_year,
        province_ids=normalized_province_ids,
        regulation_ids=normalized_regulation_ids,
        case_status=case_status,
    )
    items = _build_province_overview_items(provinces, agg)
    filter_meta = _filter_meta(case_status)
    return IndicatorsProvinceOverviewResponse(
        budget_year=budget_year,
        fiscal_start=fiscal_start,
        fiscal_end=fiscal_end,
        filter=IndicatorProvinceOverviewFilterMeta(
            case_status=filter_meta.case_status,
            latest_status_id=filter_meta.latest_status_id,
            aided_status_id=filter_meta.aided_status_id,
            province_ids=normalized_province_ids,
            regulation_ids=normalized_regulation_ids,
        ),
        items=items,
        totals=_build_province_overview_totals(items),
    )


async def fetch_indicators_export(
    session: AsyncSession,
    budget_year: int,
    province_ids: list[int] | None = None,
    type_money_category_ids: list[int] | None = None,
    regulation_ids: list[int] | None = None,
    case_status: IndicatorCaseStatus = IndicatorCaseStatus.aided,
) -> IndicatorsExportResponse:
    """JSON แถวแบนต่อเคส (dossier ครบ 10 กลุ่ม) — กฎนับเคสเดียวกับ indicators."""
    fiscal_start, fiscal_end = thai_fiscal_year_bounds_from_be(budget_year)
    normalized_province_ids = _normalize_id_list(province_ids)
    normalized_type_ids = _normalize_id_list(type_money_category_ids)
    normalized_regulation_ids = _normalize_id_list(regulation_ids)

    province_sq = _province_applicants_base(normalized_province_ids)
    aided_at_sq = _aided_at_subquery()
    address_detail_sq = _export_address_detail_subquery()
    economic_sq = _export_economic_subquery()
    diagnosis_sq = _latest_diagnosis_subquery()
    forward_sq = _latest_forward_send_subquery()
    disburse_sq = _latest_disburse_payment_subquery()
    income_agg_sq = _export_income_sources_agg_subquery()
    dependency_agg_sq = _export_dependency_agg_subquery()
    household_agg_sq = _export_household_members_agg_subquery()
    welfare_types_agg_sq = _export_welfare_type_names_agg_subquery()
    request_agg_sq = _export_request_types_agg_subquery()

    payee_person = aliased(Person, name="payee_person")
    agent_person = aliased(Person, name="agent_person")
    person_prefix = aliased(PrefixType, name="person_prefix")
    payment_bank = aliased(BankName, name="payment_bank")
    applicant_bank = aliased(BankName, name="applicant_bank")

    effective_aided_at = func.coalesce(
        aided_at_sq.c.aided_at,
        Applicant.process_completed_at,
    )
    location_sdp_id = func.coalesce(
        address_detail_sq.c.sub_district_postcode_id,
        Person.sub_district_postcode_id,
    )
    sw_license = func.coalesce(
        diagnosis_sq.c.owner_sdshv,
        CaseHandling.sw_user_sdshv,
    )
    bank_name_col = func.coalesce(payment_bank.name, applicant_bank.name)
    account_number_col = func.coalesce(
        CasePayment.account_number,
        Applicant.bank_account_no,
    )
    bank_branch_col = func.coalesce(
        CasePayment.bank_branch,
        Applicant.bank_branch_name,
    )

    stmt = select(
        Applicant.id.label("applicant_id"),
        Applicant.case_number.label("case_number"),
        Applicant.created_at.label("notified_at"),
        Applicant.is_emergency.label("is_emergency"),
        Applicant.is_existing_case.label("is_existing_case"),
        ApplicantSubmissionAudit.existing_case_source.label("existing_case_source"),
        person_prefix.name.label("prefix_name"),
        Person.first_name.label("first_name"),
        Person.last_name.label("last_name"),
        Person.cid.label("cid"),
        Person.gender.label("gender"),
        Person.birth_date.label("birth_date"),
        Applicant.age.label("age"),
        Applicant.mobile_phone.label("mobile_phone"),
        Applicant.home_phone.label("home_phone"),
        Applicant.fax_number.label("fax_number"),
        Applicant.email_address.label("email_address"),
        Applicant.is_government_officer.label("is_government_officer"),
        RequesterRelationType.name.label("requester_relation_name"),
        MaritalStatusType.name.label("marital_status_name"),
        address_detail_sq.c.house_number.label("house_number"),
        address_detail_sq.c.house_moo.label("house_moo"),
        address_detail_sq.c.alley.label("alley"),
        address_detail_sq.c.road.label("road"),
        address_detail_sq.c.latitude.label("latitude"),
        address_detail_sq.c.longitude.label("longitude"),
        SubDistrict.name.label("sub_district_name"),
        District.name.label("district_name"),
        province_sq.c.address_province_id.label("address_province_id"),
        province_sq.c.effective_province_id.label("effective_province_id"),
        economic_sq.c.occupation.label("occupation"),
        economic_sq.c.monthly_income.label("monthly_income"),
        economic_sq.c.family_occupation.label("family_occupation"),
        HousingType.name.label("housing_type_name"),
        economic_sq.c.housing_shelter.label("housing_shelter"),
        economic_sq.c.housing_rent.label("housing_rent"),
        income_agg_sq.c.income_source_names.label("income_source_names"),
        dependency_agg_sq.c.dependency_summary.label("dependency_summary"),
        household_agg_sq.c.household_members.label("household_members"),
        WelfareHistory.has_received_welfare.label("has_received_welfare"),
        WelfareHistory.received_count.label("received_count"),
        WelfareHistory.total_received_amount.label("total_received_amount"),
        welfare_types_agg_sq.c.received_welfare_type_names.label(
            "received_welfare_type_names"
        ),
        Applicant.family_distress.label("family_distress"),
        Applicant.problem_details.label("problem_details"),
        request_agg_sq.c.help_request_summary.label("help_request_summary"),
        request_agg_sq.c.request_in_kind_text.label("request_in_kind_text"),
        request_agg_sq.c.request_other_text.label("request_other_text"),
        Applicant.type_money_category_id.label("type_money_category_id"),
        TypeMoneyCategory.name.label("type_money_name"),
        TypeMoneyCategory.name_acronym.label("type_money_name_acronym"),
        TypeMoney.name.label("intake_type_money_name"),
        CaseRegulationChoice.regulation_id.label("regulation_id"),
        AnnouncementRegulation.name.label("regulation_name"),
        AnnouncementRegulation.short_name.label("regulation_short_name"),
        CaseRegulationChoice.help_kind.label("help_kind"),
        CaseRegulationChoice.money_amount.label("money_amount"),
        diagnosis_sq.c.diagnosis_text.label("diagnosis_text"),
        effective_aided_at.label("aided_at"),
        PaymentMethod.name_th.label("payment_method_name"),
        CasePayment.receive_mode.label("receive_mode"),
        payee_person.first_name.label("payee_first_name"),
        payee_person.last_name.label("payee_last_name"),
        payee_person.cid.label("payee_cid"),
        agent_person.first_name.label("agent_first_name"),
        agent_person.last_name.label("agent_last_name"),
        agent_person.cid.label("agent_cid"),
        bank_name_col.label("bank_name"),
        account_number_col.label("account_number"),
        CasePayment.account_name.label("account_name"),
        bank_branch_col.label("bank_branch"),
        CaseHandling.sw_user_sdshv.label("sw_user_sdshv"),
        diagnosis_sq.c.owner_name.label("sw_name"),
        diagnosis_sq.c.owner_position.label("sw_position"),
        sw_license.label("sw_license_sdshv"),
        diagnosis_sq.c.owner_sdshv.label("aided_org_sdshv"),
        diagnosis_sq.c.owner_organization.label("aided_org_name"),
        forward_sq.c.send_by_sdshv.label("forward_sdshv"),
        disburse_sq.c.user_sdshv.label("disburse_sdshv"),
        CaseHandling.responsible_division_id.label("responsible_division_id"),
    )
    stmt = _apply_eligible_filters(
        stmt,
        province_sq,
        budget_year,
        case_status=case_status,
        aided_at_sq=aided_at_sq,
    )
    stmt = (
        stmt.join(Person, Person.id == Applicant.persons_id)
        .outerjoin(
            person_prefix,
            person_prefix.id == Person.prefix_id,
        )
        .outerjoin(
            RequesterRelationType,
            RequesterRelationType.id == Applicant.requester_relation_id,
        )
        .outerjoin(
            MaritalStatusType,
            MaritalStatusType.id == Applicant.marital_status_id,
        )
        .outerjoin(
            ApplicantSubmissionAudit,
            ApplicantSubmissionAudit.applicant_id == Applicant.id,
        )
        .outerjoin(
            TypeMoneyCategory,
            TypeMoneyCategory.id == Applicant.type_money_category_id,
        )
        .outerjoin(
            AnnouncementRegulation,
            AnnouncementRegulation.id == CaseRegulationChoice.regulation_id,
        )
        .outerjoin(
            TypeMoney,
            TypeMoney.id == CaseHandling.type_money_id,
        )
        .outerjoin(
            CasePayment,
            CasePayment.case_handling_id == CaseHandling.id,
        )
        .outerjoin(
            PaymentMethod,
            PaymentMethod.id == CasePayment.payment_method_id,
        )
        .outerjoin(
            payee_person,
            payee_person.id == CasePayment.payee_person_id,
        )
        .outerjoin(
            agent_person,
            agent_person.id == CasePayment.agent_person_id,
        )
        .outerjoin(
            payment_bank,
            payment_bank.id == CasePayment.bank_name_id,
        )
        .outerjoin(
            applicant_bank,
            applicant_bank.id == Applicant.bank_name_id,
        )
        .outerjoin(
            WelfareHistory,
            WelfareHistory.applicant_id == Applicant.id,
        )
        .outerjoin(
            address_detail_sq,
            and_(
                address_detail_sq.c.applicant_id == Applicant.id,
                address_detail_sq.c.rn == 1,
            ),
        )
        .outerjoin(
            SubDistrictPostcode,
            SubDistrictPostcode.id == location_sdp_id,
        )
        .outerjoin(SubDistrict, SubDistrict.id == SubDistrictPostcode.sub_district_id)
        .outerjoin(District, District.id == SubDistrict.district_id)
        .outerjoin(
            economic_sq,
            and_(
                economic_sq.c.applicant_id == Applicant.id,
                economic_sq.c.rn == 1,
            ),
        )
        .outerjoin(
            HousingType,
            HousingType.id == economic_sq.c.housing_types_id,
        )
        .outerjoin(
            diagnosis_sq,
            and_(
                diagnosis_sq.c.applicant_id == Applicant.id,
                diagnosis_sq.c.rn == 1,
            ),
        )
        .outerjoin(
            forward_sq,
            and_(
                forward_sq.c.applicant_id == Applicant.id,
                forward_sq.c.rn == 1,
            ),
        )
        .outerjoin(
            disburse_sq,
            and_(
                disburse_sq.c.applicant_id == Applicant.id,
                disburse_sq.c.rn == 1,
            ),
        )
        .outerjoin(
            income_agg_sq,
            income_agg_sq.c.applicant_id == Applicant.id,
        )
        .outerjoin(
            dependency_agg_sq,
            dependency_agg_sq.c.applicant_id == Applicant.id,
        )
        .outerjoin(
            household_agg_sq,
            household_agg_sq.c.applicant_id == Applicant.id,
        )
        .outerjoin(
            welfare_types_agg_sq,
            welfare_types_agg_sq.c.applicant_id == Applicant.id,
        )
        .outerjoin(
            request_agg_sq,
            request_agg_sq.c.applicant_id == Applicant.id,
        )
    )
    if normalized_type_ids is not None:
        stmt = stmt.where(Applicant.type_money_category_id.in_(normalized_type_ids))
    if normalized_regulation_ids is not None:
        stmt = stmt.where(CaseRegulationChoice.regulation_id.in_(normalized_regulation_ids))

    stmt = stmt.order_by(
        province_sq.c.effective_province_id.asc(),
        Applicant.id.asc(),
    )

    result = await session.execute(stmt)
    rows = result.all()

    province_id_set: set[int] = set()
    for row in rows:
        province_id_set.add(int(row.address_province_id))
        province_id_set.add(int(row.effective_province_id))
    province_name_by_id: dict[int, str] = {}
    if province_id_set:
        province_rows = await session.execute(
            select(Province).where(Province.id.in_(province_id_set))
        )
        for province in province_rows.scalars().all():
            province_name_by_id[province.id] = province.name

    items: list[IndicatorExportCaseItem] = []
    for row in rows:
        address_province_id = int(row.address_province_id)
        effective_province_id = int(row.effective_province_id)
        address_province_name = province_name_by_id.get(
            address_province_id,
            str(address_province_id),
        )
        money_amount = _format_money(row.money_amount)
        monthly_income = _format_money(row.monthly_income)
        housing_rent = _format_money(row.housing_rent)
        total_received_amount = _format_money(row.total_received_amount)
        payee_full_name, payee_cid, payee_mobile = _resolve_export_payee(
            receive_mode=row.receive_mode,
            applicant_first_name=row.first_name,
            applicant_last_name=row.last_name,
            applicant_cid=row.cid,
            applicant_mobile=row.mobile_phone,
            payee_first_name=row.payee_first_name,
            payee_last_name=row.payee_last_name,
            payee_cid=row.payee_cid,
            agent_first_name=row.agent_first_name,
            agent_last_name=row.agent_last_name,
            agent_cid=row.agent_cid,
        )
        household_members = _map_household_members(row.household_members)
        items.append(
            IndicatorExportCaseItem(
                applicant_id=int(row.applicant_id),
                case_channel=EXPORT_CASE_CHANNEL,
                case_number=row.case_number,
                notified_at=format_thai_date(row.notified_at),
                is_emergency=row.is_emergency,
                is_existing_case=row.is_existing_case,
                existing_case_source=row.existing_case_source,
                prefix_name=row.prefix_name,
                first_name=row.first_name,
                last_name=row.last_name,
                cid=row.cid,
                gender=row.gender,
                birth_date=format_thai_date(row.birth_date) or "",
                age=row.age,
                mobile_phone=row.mobile_phone,
                home_phone=row.home_phone,
                fax_number=row.fax_number,
                email_address=row.email_address,
                is_government_officer=row.is_government_officer,
                requester_relation_name=row.requester_relation_name,
                marital_status_name=row.marital_status_name,
                house_number=row.house_number,
                house_moo=row.house_moo,
                alley=row.alley,
                road=row.road,
                sub_district_name=row.sub_district_name,
                district_name=row.district_name,
                address_province_id=address_province_id,
                address_province_name=address_province_name,
                effective_province_id=effective_province_id,
                effective_province_name=province_name_by_id.get(
                    effective_province_id,
                    str(effective_province_id),
                ),
                latitude=row.latitude,
                longitude=row.longitude,
                address_full=_build_address_full(
                    house_number=row.house_number,
                    house_moo=row.house_moo,
                    alley=row.alley,
                    road=row.road,
                    sub_district_name=row.sub_district_name,
                    district_name=row.district_name,
                    province_name=address_province_name,
                ),
                occupation=row.occupation,
                monthly_income=monthly_income,
                family_occupation=row.family_occupation,
                household_member_count=len(household_members),
                housing_type_name=row.housing_type_name,
                housing_shelter=row.housing_shelter,
                housing_rent=housing_rent,
                income_source_names=row.income_source_names,
                dependency_summary=row.dependency_summary,
                household_members=household_members,
                has_received_welfare=row.has_received_welfare,
                received_count=row.received_count,
                total_received_amount=total_received_amount,
                received_welfare_type_names=row.received_welfare_type_names,
                family_distress=row.family_distress,
                problem_details=row.problem_details,
                help_request_summary=row.help_request_summary,
                request_in_kind_text=row.request_in_kind_text,
                request_other_text=row.request_other_text,
                type_money_category_id=row.type_money_category_id,
                type_money_name=row.type_money_name,
                type_money_name_acronym=row.type_money_name_acronym,
                intake_type_money_name=row.intake_type_money_name,
                regulation_id=row.regulation_id,
                regulation_name=row.regulation_name,
                regulation_short_name=row.regulation_short_name,
                help_kind=row.help_kind,
                money_amount=money_amount,
                diagnosis_text=row.diagnosis_text,
                aided_at=row.aided_at,
                payment_method_name=row.payment_method_name,
                receive_mode=row.receive_mode,
                payee_full_name=payee_full_name,
                payee_cid=payee_cid,
                payee_mobile=payee_mobile,
                bank_name=row.bank_name,
                account_number=row.account_number,
                account_name=row.account_name,
                bank_branch=row.bank_branch,
                sw_user_sdshv=row.sw_user_sdshv,
                sw_name=row.sw_name,
                sw_position=row.sw_position,
                sw_license_sdshv=row.sw_license_sdshv,
                aided_org_sdshv=_blank_to_none(row.aided_org_sdshv),
                aided_org_name=_blank_to_none(row.aided_org_name),
                forward_sdshv=_blank_to_none(row.forward_sdshv),
                disburse_sdshv=_blank_to_none(row.disburse_sdshv),
                responsible_division_id=(
                    int(row.responsible_division_id)
                    if row.responsible_division_id is not None
                    else None
                ),
                responsible_division_name=division_name_for_id(
                    row.responsible_division_id
                ),
            )
        )

    filter_meta = _filter_meta(case_status)
    return IndicatorsExportResponse(
        budget_year=budget_year,
        fiscal_start=fiscal_start,
        fiscal_end=fiscal_end,
        filter=IndicatorExportFilterMeta(
            case_status=filter_meta.case_status,
            latest_status_id=filter_meta.latest_status_id,
            aided_status_id=filter_meta.aided_status_id,
            province_ids=normalized_province_ids,
            type_money_category_ids=normalized_type_ids,
            regulation_ids=normalized_regulation_ids,
        ),
        items=items,
        totals=_build_export_totals(items),
    )
