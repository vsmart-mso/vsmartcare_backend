"""สคีมารายการคำร้องสำหรับหน้าจอเจ้าหน้าที่."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CaseForStaffRead(BaseModel):
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


class CaseForStaffListResponse(BaseModel):
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    total_applicants: int = Field(..., ge=0, description="จำนวน Applicant ทั้งหมดในจังหวัด")
    filtered_applicants: int = Field(..., ge=0, description="จำนวน Applicant หลังใช้ filter")
    items: list[CaseForStaffRead] = Field(default_factory=list)


class CaseForStaffFinanceRead(CaseForStaffRead):
    bank_name_id: int | None = Field(None, ge=1)
    bank_code: str | None = Field(None, max_length=10)
    bank_account_no: str | None = Field(None, max_length=50)
    email_address: str | None = Field(None, max_length=255)
    mobile_phone: str | None = Field(None, max_length=20)
    money_amount: Decimal | None = Field(None, ge=0)
    dda_ref: str | None = Field(None, max_length=255)
    count_037: int = Field(0, ge=0)
    count_038: int = Field(0, ge=0)
    is_037_or_038: bool | None = None


class CaseForStaffFinanceListResponse(BaseModel):
    province_id: int
    province_name: str = Field(..., min_length=1, max_length=255)
    total_applicants: int = Field(..., ge=0)
    filtered_applicants: int = Field(..., ge=0)
    items: list[CaseForStaffFinanceRead] = Field(default_factory=list)
