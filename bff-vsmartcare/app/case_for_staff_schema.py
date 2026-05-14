"""สคีมารายการคำร้องสำหรับหน้าจอเจ้าหน้าที่."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CaseForStaffRead(BaseModel):
    case_number: str | None = Field(None, max_length=100)
    current_status: str | None = None
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
