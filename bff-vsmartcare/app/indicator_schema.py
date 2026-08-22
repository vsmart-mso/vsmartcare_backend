"""สคีมาตัวชี้วัดเงินช่วยเหลือ — mirror case-service indicators response."""

from __future__ import annotations

from datetime import date, datetime
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


class IndicatorExportFilterMeta(IndicatorFilterMeta):
    province_ids: list[int] | None = None
    type_money_category_ids: list[int] | None = None
    regulation_ids: list[int] | None = None


class IndicatorApproverSdshvItem(BaseModel):
    user_sdshv: str | None = None
    case_count: int = Field(..., ge=0)
    total_money_amount: Decimal = Field(..., ge=0)


class IndicatorRegulationBreakdownItem(BaseModel):
    regulation_id: int | None = None
    regulation_name: str | None = None
    regulation_short_name: str | None = None
    case_count: int = Field(..., ge=0)
    total_money_amount: Decimal = Field(..., ge=0)
    by_approver_sdshv: list[IndicatorApproverSdshvItem] = Field(default_factory=list)


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


class IndicatorExportCaseItem(BaseModel):
    applicant_id: int
    case_number: str | None = None
    first_name: str
    last_name: str
    cid: str
    gender: str | None = None
    birth_date: date
    age: int | None = None
    mobile_phone: str | None = None
    house_number: str | None = None
    house_moo: str | None = None
    alley: str | None = None
    road: str | None = None
    sub_district_name: str | None = None
    district_name: str | None = None
    address_province_id: int
    address_province_name: str
    effective_province_id: int
    effective_province_name: str
    occupation: str | None = None
    monthly_income: Decimal | None = None
    family_distress: str | None = None
    type_money_category_id: int | None = None
    type_money_name: str | None = None
    type_money_name_acronym: str | None = None
    regulation_id: int | None = None
    regulation_name: str | None = None
    regulation_short_name: str | None = None
    help_kind: str | None = None
    money_amount: Decimal | None = None
    aided_at: datetime | None = None
    sw_user_sdshv: str | None = None


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
    filter: IndicatorFilterMeta
    items: list[IndicatorProvinceItem]
    totals: IndicatorTotals


class IndicatorsExportResponse(BaseModel):
    budget_year: int
    fiscal_start: datetime
    fiscal_end: datetime
    filter: IndicatorExportFilterMeta
    items: list[IndicatorExportCaseItem]
    totals: IndicatorTotals
