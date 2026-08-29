"""สคีมาแดชบอร์ด — สอดคล้องกับ dashboard-service `app/schemas.py`."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ProcessTrafficColor = Literal["green", "yellow", "orange", "red"]


class DashboardStatusCount(BaseModel):
    current_status_id: int
    label: str
    color: str
    count: int = Field(..., ge=0)
    percent: float = Field(..., ge=0, le=100)


class DashboardOverviewRead(BaseModel):
    province_id: int
    province_name: str
    total: int = Field(..., ge=0)
    updated_at: datetime
    statuses: list[DashboardStatusCount]


class DashboardDistrictRow(BaseModel):
    district_id: int
    district_code: str | None = None
    district_name: str
    status_counts: dict[str, int]
    total: int = Field(..., ge=0)


class DashboardDistrictsRead(BaseModel):
    province_id: int
    province_name: str
    page: int
    page_size: int
    total_items: int
    total_pages: int
    items: list[DashboardDistrictRow]


class DashboardNationalOverviewRead(BaseModel):
    total: int = Field(..., ge=0)
    updated_at: datetime
    statuses: list[DashboardStatusCount]


class DashboardProvinceRow(BaseModel):
    province_id: int
    province_name: str
    status_counts: dict[str, int]
    total: int = Field(..., ge=0)


class DashboardProvincesRead(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    items: list[DashboardProvinceRow]


class DashboardSubDistrictRow(BaseModel):
    sub_district_id: int
    sub_district_code: str | None = None
    sub_district_name: str
    status_counts: dict[str, int]
    total: int = Field(..., ge=0)


class DashboardSubDistrictsRead(BaseModel):
    district_id: int
    district_name: str
    province_id: int
    province_name: str
    page: int
    page_size: int
    total_items: int
    total_pages: int
    items: list[DashboardSubDistrictRow]


class DashboardCaseRow(BaseModel):
    applicant_id: int
    case_number: str | None = Field(None, max_length=100)
    current_status_id: int | None = None
    current_status: str | None = None
    current_status_color: str | None = Field(None, max_length=32)
    type_money_id: int | None = None
    type_money_id_name: str | None = Field(None, max_length=255)
    type_money_id_color: str | None = Field(None, max_length=32)
    type_money_name_acronym: str | None = Field(None, max_length=255)
    sw_explorer_sdshv: str | None = Field(None, max_length=255)
    firstname: str = Field(..., min_length=1, max_length=255)
    lastname: str = Field(..., min_length=1, max_length=255)
    cid: str = Field(..., min_length=13, max_length=13)
    person_age: int = Field(..., ge=0)
    datetime_create: datetime
    is_emergency: bool
    is_existing_case: bool
    time_count_process: int | None = Field(None, ge=0)
    process_started_at: datetime | None = None
    process_completed_at: datetime | None = None
    process_sla_days: int | None = Field(None, ge=1)
    process_elapsed_days: int | None = Field(None, ge=0)
    process_remaining_days: int | None = None
    process_traffic_color: ProcessTrafficColor | None = None
    process_is_overdue: bool | None = None
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    current_address_province_id: int | None = None
    current_address_province_name: str | None = Field(None, max_length=255)
    district_id: int
    district_name: str = Field(..., min_length=1, max_length=255)
    subdistrict_id: int
    subdistrict_name: str = Field(..., min_length=1, max_length=255)
    subdistrict_postcode_id: int
    postcode: str = Field(..., min_length=1, max_length=10)
    count_037: int = Field(0, ge=0)
    count_038: int = Field(0, ge=0)
    is_037_or_038: bool | None = None
    have_dda_ref: bool = False
    is_approved: bool = False
    is_disabled: bool = False
    previous_status_id: int | None = None
    is_return_edit_resubmitted: bool = False
    is_pmj_rejected: bool = False
    pmj_reject_reason: str | None = None
    prior_self_submit_case_numbers: list[str] = Field(default_factory=list)
    self_submit_fiscal_year_count: int = Field(0, ge=0)
    self_submit_fiscal_year_case_numbers: list[str] = Field(default_factory=list)
    responsible_division_id: int | None = Field(None, ge=1)
    responsible_division_name: str | None = None
    require_ktb_corporate: bool = True
    require_ktb_reason: str = Field("NEW_CASE", max_length=32)
    existing_case_source: str | None = Field(None, max_length=16)
    existing_case_detected_sources: list[str] | None = None
    existing_case_ref_id: int | None = None
    existing_case_province_id: int | None = None
    existing_case_province_name: str | None = Field(None, max_length=255)
    submission_province_id: int | None = None
    submission_province_name: str | None = Field(None, max_length=255)
    is_account_changed: bool | None = None
    has_ktb_evidence: bool = False
    prior_ktb_reuse_applicant_id: int | None = None


class DashboardCasesRead(BaseModel):
    province_ids: list[int] | None = None
    page: int
    page_size: int
    total_items: int
    total_pages: int
    items: list[DashboardCaseRow]
