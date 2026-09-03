"""สคีมาตัวชี้วัดเงินช่วยเหลือ — mirror case-service indicators response."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class IndicatorCaseStatus(str, Enum):
    aided = "aided"
    forwarded = "forwarded"


class IndicatorFilterMeta(BaseModel):
    case_status: IndicatorCaseStatus
    latest_status_id: int
    aided_status_id: int


class IndicatorNationwideFilterMeta(IndicatorFilterMeta):
    province_ids: list[int] | None = None
    type_money_category_ids: list[int] | None = None


class IndicatorExportFilterMeta(IndicatorFilterMeta):
    province_ids: list[int] | None = None
    type_money_category_ids: list[int] | None = None
    regulation_ids: list[int] | None = None


class IndicatorDisburseSdshvItem(BaseModel):
    user_sdshv: str | None = Field(
        None,
        description="ผู้เบิกจ่ายจาก welfare_payment.user_sdshv แถวล่าสุด — null = ไม่ระบุ",
    )
    case_count: int = Field(..., ge=0)
    total_money_amount: Decimal = Field(..., ge=0)


class IndicatorRegulationBreakdownItem(BaseModel):
    regulation_id: int | None = None
    regulation_name: str | None = None
    regulation_short_name: str | None = None
    case_count: int = Field(..., ge=0)
    total_money_amount: Decimal = Field(..., ge=0)
    by_disburse_sdshv: list[IndicatorDisburseSdshvItem] = Field(
        default_factory=list,
        description="แยกตามผู้เบิกจ่าย welfare_payment.user_sdshv",
    )


class IndicatorMoneyItem(BaseModel):
    type_money_category_id: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=255)
    name_acronym: str = Field(..., min_length=1, max_length=255)
    name_acrovym_eng: str = Field(..., min_length=1, max_length=255)
    case_count: int = Field(..., ge=0)
    total_money_amount: Decimal = Field(..., ge=0)
    by_regulation: list[IndicatorRegulationBreakdownItem] = Field(default_factory=list)


class IndicatorTotals(BaseModel):
    case_count: int = Field(..., ge=0)
    total_money_amount: Decimal = Field(..., ge=0)


class IndicatorProvinceItem(BaseModel):
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    case_count: int = Field(..., ge=0)
    total_money_amount: Decimal = Field(..., ge=0)


class IndicatorExportHouseholdMemberItem(BaseModel):
    """สมาชิกครัวเรือนหนึ่งคนใน export — mirror case-service."""

    seq: int
    prefix_name: str | None = None
    first_name: str
    last_name: str
    cid: str | None = None
    date_of_birth: str | None = None
    age: int | None = None
    relation_name: str | None = None
    occupation: str | None = None
    monthly_income: str | None = None
    physical_condition: str | None = None
    self_care: str | None = None


class IndicatorExportCaseItem(BaseModel):
    """Flat dossier row — mirror case-service. ไม่ส่งลำดับ / จำนวนเงินที่ขอ."""

    applicant_id: int
    case_channel: str = "พม.CARE"
    case_number: str | None = None
    notified_at: str | None = None
    is_emergency: bool | None = None
    is_existing_case: bool | None = None
    existing_case_source: str | None = None
    prefix_name: str | None = None
    first_name: str
    last_name: str
    cid: str
    gender: str | None = None
    birth_date: str
    age: int | None = None
    mobile_phone: str | None = None
    home_phone: str | None = None
    fax_number: str | None = None
    email_address: str | None = None
    is_government_officer: bool | None = None
    requester_relation_name: str | None = None
    marital_status_name: str | None = None
    house_number: str | None = None
    house_moo: str | None = None
    house_name: str | None = None
    alley: str | None = None
    sub_lane: str | None = None
    road: str | None = None
    sub_district_name: str | None = None
    district_name: str | None = None
    postcode: str | None = None
    address_province_id: int
    address_province_name: str
    effective_province_id: int
    effective_province_name: str
    latitude: str | None = None
    longitude: str | None = None
    nearby_landmark: str | None = None
    address_full: str | None = None
    occupation: str | None = None
    monthly_income: str | None = None
    family_occupation: str | None = None
    household_member_count: int | None = None
    housing_type_name: str | None = None
    housing_shelter: str | None = None
    housing_rent: str | None = None
    income_source_names: str | None = None
    dependency_summary: str | None = None
    household_members: list[IndicatorExportHouseholdMemberItem] = Field(
        default_factory=list,
    )
    has_received_welfare: bool | None = None
    received_count: int | None = None
    total_received_amount: str | None = None
    received_welfare_type_names: str | None = None
    family_distress: str | None = None
    problem_details: str | None = None
    help_request_summary: str | None = None
    help_request_money: bool = False
    help_request_kind: bool = False
    help_request_kind_text: str | None = None
    help_request_other: bool = False
    help_request_other_text: str | None = None
    type_money_category_id: int | None = None
    type_money_name: str | None = None
    type_money_name_acronym: str | None = None
    intake_type_money_name: str | None = None
    regulation_id: int | None = None
    regulation_name: str | None = None
    regulation_short_name: str | None = None
    help_kind: str | None = None
    money_amount: str | None = None
    diagnosis_text: str | None = None
    aided_at: datetime | None = None
    payment_method_name: str | None = None
    receive_mode: str | None = None
    payee_full_name: str | None = None
    payee_cid: str | None = None
    payee_mobile: str | None = None
    bank_name: str | None = None
    bank_code: str | None = None
    account_number: str | None = None
    account_name: str | None = None
    bank_branch: str | None = None
    sw_user_sdshv: str | None = None
    sw_name: str | None = None
    sw_position: str | None = None
    sw_license_sdshv: str | None = None
    aided_org_sdshv: str | None = None
    aided_org_name: str | None = None
    forward_sdshv: str | None = None
    disburse_sdshv: str | None = None
    responsible_division_id: int | None = None
    responsible_division_name: str | None = None


class IndicatorsByProvinceResponse(BaseModel):
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    budget_year: int
    fiscal_start: datetime
    fiscal_end: datetime
    filter: IndicatorFilterMeta
    items: list[IndicatorMoneyItem]
    totals: IndicatorTotals


class IndicatorsNationwideResponse(BaseModel):
    budget_year: int
    province_ids: list[int] | None = None
    fiscal_start: datetime
    fiscal_end: datetime
    filter: IndicatorNationwideFilterMeta
    items: list[IndicatorProvinceItem]
    totals: IndicatorTotals


class IndicatorsExportResponse(BaseModel):
    budget_year: int
    fiscal_start: datetime
    fiscal_end: datetime
    filter: IndicatorExportFilterMeta
    items: list[IndicatorExportCaseItem]
    totals: IndicatorTotals


class IndicatorProvinceOverviewFilterMeta(IndicatorFilterMeta):
    province_ids: list[int] | None = None
    regulation_ids: list[int] | None = None


class IndicatorProvinceOverviewItem(BaseModel):
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    total_budget_amount: Decimal = Field(..., ge=0)
    pending_service_case_count: int = Field(..., ge=0)
    disbursement_case_count: int = Field(..., ge=0)
    aided_case_count: int = Field(..., ge=0)


class IndicatorProvinceOverviewTotals(BaseModel):
    total_budget_amount: Decimal = Field(..., ge=0)
    pending_service_case_count: int = Field(..., ge=0)
    disbursement_case_count: int = Field(..., ge=0)
    aided_case_count: int = Field(..., ge=0)


class IndicatorsProvinceOverviewResponse(BaseModel):
    budget_year: int
    fiscal_start: datetime
    fiscal_end: datetime
    filter: IndicatorProvinceOverviewFilterMeta
    items: list[IndicatorProvinceOverviewItem]
    totals: IndicatorProvinceOverviewTotals
