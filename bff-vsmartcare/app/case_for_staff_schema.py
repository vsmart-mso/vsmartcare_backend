"""สคีมารายการคำร้องสำหรับหน้าจอเจ้าหน้าที่."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from typing import Literal, Optional

from pydantic import BaseModel, Field

ProcessTrafficColor = Literal["green", "yellow", "orange", "red"]


class ProcessSlaFields(BaseModel):
    process_started_at: datetime | None = None
    process_sla_days: int | None = Field(None, ge=1)
    process_elapsed_days: int | None = Field(None, ge=0)
    process_remaining_days: int | None = None
    process_traffic_color: ProcessTrafficColor | None = None
    process_is_overdue: bool | None = None


class CaseForStaffRead(ProcessSlaFields):
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
    person_age: int = Field(..., ge=0, description="อายุ (ปี) คำนวณจาก persons.birth_date ณ วันที่เรียก API")
    datetime_create: datetime
    is_emergency: bool
    is_existing_case: bool
    time_count_process: int | None = Field(None, ge=0)
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    district_id: int
    district_name: str = Field(..., min_length=1, max_length=255)
    subdistrict_id: int
    subdistrict_name: str = Field(..., min_length=1, max_length=255)
    subdistrict_postcode_id: int
    postcode: str = Field(..., min_length=1, max_length=10)
    count_037: int = Field(0, ge=0, description="จำนวนแถว welfare_payment ที่ is_037_or_038 = false (037)")
    count_038: int = Field(
        0,
        ge=0,
        description="จำนวนครั้งที่บันทึก 038 (นับแถว welfare_payment ที่ is_037_or_038 = true)",
    )
    is_037_or_038: bool | None = None
    have_dda_ref: bool = False
    is_approved: bool = Field(
        False,
        description="true เมื่อ applicant มีแถว approve_case ที่ approve_status = true",
    )


class CaseForStaffListResponse(BaseModel):
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    total_applicants: int = Field(..., ge=0, description="จำนวน Applicant ทั้งหมดในจังหวัด")
    filtered_applicants: int = Field(..., ge=0, description="จำนวน Applicant หลังใช้ filter")
    items: list[CaseForStaffRead] = Field(default_factory=list)


class CaseForStaffStatusSummaryResponse(BaseModel):
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    total_applicants: int = Field(..., ge=0)
    social_worker_pending: int = Field(0, ge=0)
    withdrawing_in_progress: int = Field(0, ge=0)
    pmj_pending_approve: int = Field(0, ge=0)
    finance_pending: int = Field(0, ge=0)


class CaseForStaffFinanceRead(ProcessSlaFields):
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
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
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
    dda_ref: str | None = Field(None, max_length=255)
    bank_name_id: int | None = None
    bank_code: str | None = Field(None, max_length=32)
    bank_account_no: str | None = Field(None, max_length=50)
    email_address: str | None = Field(None, max_length=255)
    mobile_phone: str | None = Field(None, max_length=20)
    money_amount: Decimal | None = None


class CaseForStaffFinanceListResponse(BaseModel):
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    total_applicants: int = Field(..., ge=0)
    filtered_applicants: int = Field(..., ge=0)
    items: list[CaseForStaffFinanceRead] = Field(default_factory=list)


class CaseForStaffApplicantStaffFieldsRead(ProcessSlaFields):
    """ผลลัพธ์หลัง PATCH applicant-staff-fields — mirror case-service."""

    applicant_id: int
    type_money_category_id: int | None = None
    type_money_name: str | None = Field(None, max_length=255)
    type_money_name_acronym: str | None = Field(None, max_length=255)
    type_money_color: str | None = Field(None, max_length=32)
    sw_explorer_sdshv: str | None = Field(None, max_length=255)
    is_emergency: bool = False
    time_count_process: int | None = Field(None, ge=0)
    updated_at: datetime


class ArticleCreateBody(BaseModel):
    """Mirror case-service ArticleCreate — เนื้อหา article เท่านั้น (ไม่รวมอนุมัติ)."""

    applicant_id: int = Field(..., ge=1)
    service_vsmart_id: Optional[str] = Field(None, max_length=255)
    phone_service: Optional[str] = Field(None, max_length=255)
    at: Optional[str] = Field(None, max_length=255)
    date_at: Optional[date] = None
    title: Optional[str] = Field(None, max_length=255)
    refer_vsmart_id: Optional[str] = Field(None, max_length=255)
    original_story: Optional[str] = None
    fact_story: Optional[str] = None
    laws: Optional[str] = None
    consider: Optional[str] = None
    suggestion: Optional[str] = None


class ArticleUpdateBody(BaseModel):
    """Mirror case-service ArticleUpdate."""

    service_vsmart_id: Optional[str] = Field(None, max_length=255)
    phone_service: Optional[str] = Field(None, max_length=255)
    at: Optional[str] = Field(None, max_length=255)
    date_at: Optional[date] = None
    title: Optional[str] = Field(None, max_length=255)
    refer_vsmart_id: Optional[str] = Field(None, max_length=255)
    original_story: Optional[str] = None
    fact_story: Optional[str] = None
    laws: Optional[str] = None
    consider: Optional[str] = None
    suggestion: Optional[str] = None
