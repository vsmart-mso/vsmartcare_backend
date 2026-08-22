"""สรุปตัวชี้วัดเงินช่วยเหลือ พม Care 6 ประเภท (รายจังหวัด / รวมทั้งประเทศ)."""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from ..constants.current_status import (
    CURRENT_STATUS_AID_COMPLETED,
    CURRENT_STATUS_MSO_FORWARDED,
)
from ..models.address import Address
from ..models.applicant import Applicant
from ..models.economic import EconomicInfo
from ..models.geo import District, Postcode, Province, SubDistrict, SubDistrictPostcode
from ..models.intake import AnnouncementRegulation, CaseHandling, CaseRegulationChoice
from ..models.lookup import TypeMoneyCategory
from ..models.payment import ApproveCase
from ..models.person import Person
from ..models.status_log import WelfareRequestStatus
from ..schemas.indicators import (
    IndicatorApproverSdshvItem,
    IndicatorCaseStatus,
    IndicatorExportCaseItem,
    IndicatorExportFilterMeta,
    IndicatorFilterMeta,
    IndicatorMoneyItem,
    IndicatorProvinceItem,
    IndicatorRegulationBreakdownItem,
    IndicatorTotals,
    IndicatorsByProvinceResponse,
    IndicatorsExportResponse,
    IndicatorsNationwideResponse,
)
from ..utils.budget_year import thai_fiscal_year_bounds_from_be
from .dwf_scope import SOR_KOR_TYPE_MONEY_ID, dwf_groups

INDICATOR_TYPE_MONEY_CATEGORY_IDS: tuple[int, ...] = (1, 2, 3, 4, 5, 6)
# ดย. / DCY — เงินสงเคราะห์เด็กในครอบครัวยากจน
DCY_TYPE_MONEY_ID = 2

# case_status=aided — ช่วยเหลือแล้วเท่านั้น (4)
INDICATOR_AIDED_LATEST_STATUS_IDS: tuple[int, ...] = (
    CURRENT_STATUS_AID_COMPLETED,
)
# case_status=forwarded — ส่งต่อกระทรวงแล้ว
INDICATOR_FORWARDED_LATEST_STATUS_IDS: tuple[int, ...] = (
    CURRENT_STATUS_MSO_FORWARDED,
)


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
            func.row_number()
            .over(
                partition_by=EconomicInfo.applicant_id,
                order_by=[EconomicInfo.id.asc()],
            )
            .label("rn"),
        )
        .subquery()
    )


def _build_export_totals(items: list[IndicatorExportCaseItem]) -> IndicatorTotals:
    return IndicatorTotals(
        case_count=len(items),
        total_money_amount=sum(
            (i.money_amount if i.money_amount is not None else Decimal("0") for i in items),
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
) -> dict[int, tuple[int, Decimal]]:
    province_sq = _province_applicants_base(province_ids)
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
    ).group_by(province_sq.c.effective_province_id)

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
    case_status: IndicatorCaseStatus = IndicatorCaseStatus.aided,
) -> IndicatorsNationwideResponse:
    fiscal_start, fiscal_end = thai_fiscal_year_bounds_from_be(budget_year)
    normalized_ids = _normalize_id_list(province_ids)
    provinces = await _load_provinces(session, normalized_ids)
    agg = await _aggregate_by_province(
        session,
        budget_year=budget_year,
        province_ids=normalized_ids,
        case_status=case_status,
    )
    items = _build_province_items(provinces, agg)
    return IndicatorsNationwideResponse(
        budget_year=budget_year,
        province_ids=normalized_ids,
        fiscal_start=fiscal_start,
        fiscal_end=fiscal_end,
        filter=_filter_meta(case_status),
        items=items,
        totals=_build_totals(items),
    )


async def fetch_indicators_export(
    session: AsyncSession,
    budget_year: int,
    province_ids: list[int] | None = None,
    type_money_category_ids: list[int] | None = None,
    regulation_ids: list[int] | None = None,
    case_status: IndicatorCaseStatus = IndicatorCaseStatus.aided,
) -> IndicatorsExportResponse:
    """JSON แถวต่อเคสสำหรับ FE Excel — กฎนับเคสเดียวกับ indicators + optional หมวด/ระเบียบ."""
    fiscal_start, fiscal_end = thai_fiscal_year_bounds_from_be(budget_year)
    normalized_province_ids = _normalize_id_list(province_ids)
    normalized_type_ids = _normalize_id_list(type_money_category_ids)
    normalized_regulation_ids = _normalize_id_list(regulation_ids)

    province_sq = _province_applicants_base(normalized_province_ids)
    aided_at_sq = _aided_at_subquery()
    address_detail_sq = _export_address_detail_subquery()
    economic_sq = _export_economic_subquery()
    effective_aided_at = func.coalesce(
        aided_at_sq.c.aided_at,
        Applicant.process_completed_at,
    )
    location_sdp_id = func.coalesce(
        address_detail_sq.c.sub_district_postcode_id,
        Person.sub_district_postcode_id,
    )

    stmt = select(
        Applicant.id.label("applicant_id"),
        Applicant.case_number.label("case_number"),
        Person.first_name.label("first_name"),
        Person.last_name.label("last_name"),
        Person.cid.label("cid"),
        Person.gender.label("gender"),
        Person.birth_date.label("birth_date"),
        Applicant.age.label("age"),
        Applicant.mobile_phone.label("mobile_phone"),
        address_detail_sq.c.house_number.label("house_number"),
        address_detail_sq.c.house_moo.label("house_moo"),
        address_detail_sq.c.alley.label("alley"),
        address_detail_sq.c.road.label("road"),
        SubDistrict.name.label("sub_district_name"),
        District.name.label("district_name"),
        province_sq.c.address_province_id.label("address_province_id"),
        province_sq.c.effective_province_id.label("effective_province_id"),
        economic_sq.c.occupation.label("occupation"),
        economic_sq.c.monthly_income.label("monthly_income"),
        Applicant.family_distress.label("family_distress"),
        Applicant.type_money_category_id.label("type_money_category_id"),
        TypeMoneyCategory.name.label("type_money_name"),
        TypeMoneyCategory.name_acronym.label("type_money_name_acronym"),
        CaseRegulationChoice.regulation_id.label("regulation_id"),
        AnnouncementRegulation.name.label("regulation_name"),
        AnnouncementRegulation.short_name.label("regulation_short_name"),
        CaseRegulationChoice.help_kind.label("help_kind"),
        CaseRegulationChoice.money_amount.label("money_amount"),
        effective_aided_at.label("aided_at"),
        CaseHandling.sw_user_sdshv.label("sw_user_sdshv"),
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
            TypeMoneyCategory,
            TypeMoneyCategory.id == Applicant.type_money_category_id,
        )
        .outerjoin(
            AnnouncementRegulation,
            AnnouncementRegulation.id == CaseRegulationChoice.regulation_id,
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
        money_amount = (
            _to_decimal(row.money_amount) if row.money_amount is not None else None
        )
        monthly_income = (
            _to_decimal(row.monthly_income) if row.monthly_income is not None else None
        )
        items.append(
            IndicatorExportCaseItem(
                applicant_id=int(row.applicant_id),
                case_number=row.case_number,
                first_name=row.first_name,
                last_name=row.last_name,
                cid=row.cid,
                gender=row.gender,
                birth_date=row.birth_date,
                age=row.age,
                mobile_phone=row.mobile_phone,
                house_number=row.house_number,
                house_moo=row.house_moo,
                alley=row.alley,
                road=row.road,
                sub_district_name=row.sub_district_name,
                district_name=row.district_name,
                address_province_id=address_province_id,
                address_province_name=province_name_by_id.get(
                    address_province_id,
                    str(address_province_id),
                ),
                effective_province_id=effective_province_id,
                effective_province_name=province_name_by_id.get(
                    effective_province_id,
                    str(effective_province_id),
                ),
                occupation=row.occupation,
                monthly_income=monthly_income,
                family_distress=row.family_distress,
                type_money_category_id=row.type_money_category_id,
                type_money_name=row.type_money_name,
                type_money_name_acronym=row.type_money_name_acronym,
                regulation_id=row.regulation_id,
                regulation_name=row.regulation_name,
                regulation_short_name=row.regulation_short_name,
                help_kind=row.help_kind,
                money_amount=money_amount,
                aided_at=row.aided_at,
                sw_user_sdshv=row.sw_user_sdshv,
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
