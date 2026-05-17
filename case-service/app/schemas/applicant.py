"""Pydantic schemas สำหรับ applicants (ผู้ขอรับสวัสดิการ).

ข้อมูลชื่อ/เลขบัตรอยู่ที่ Person — ใช้ persons_id อ้างอิง
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .process_sla import ProcessSlaFields


class ApplicantBase(BaseModel):
    persons_id: int
    requester_relation_id: int
    marital_status_id: int

    mobile_phone: str | None = Field(None, max_length=20)
    home_phone: str | None = Field(None, max_length=20)
    fax_number: str | None = Field(None, max_length=20)
    email_address: EmailStr | None = None

    is_government_officer: bool = False

    problem_details: str | None = None

    bank_name_id: int | None = Field(None, ge=1)
    bank_account_no: str | None = Field(None, max_length=50)
    type_money_category_id: int | None = Field(None, ge=1)
    sw_explorer_sdshv: str | None = Field(None, max_length=255)

    time_count_process: int | None = Field(None, ge=0)

    is_emergency: bool = False
    is_existing_case: bool = False

    age: int | None = Field(None, ge=0)


class ApplicantCreate(ApplicantBase):
    pass


class ApplicantUpdate(BaseModel):
    persons_id: int | None = None
    requester_relation_id: int | None = None
    marital_status_id: int | None = None
    mobile_phone: str | None = Field(None, max_length=20)
    home_phone: str | None = Field(None, max_length=20)
    fax_number: str | None = Field(None, max_length=20)
    email_address: EmailStr | None = None
    is_government_officer: bool | None = None
    bank_name_id: int | None = Field(None, ge=1)
    bank_account_no: str | None = Field(None, max_length=50)
    type_money_category_id: int | None = Field(None, ge=1)
    sw_explorer_sdshv: str | None = Field(None, max_length=255)
    time_count_process: int | None = Field(None, ge=0)
    is_emergency: bool | None = None
    is_existing_case: bool | None = None
    problem_details: str | None = None
    age: int | None = Field(None, ge=0)


class ApplicantRead(ApplicantBase, ProcessSlaFields):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ApplicantDeleteByCidResponse(BaseModel):
    cid: str = Field(..., min_length=13, max_length=13)
    person_id: int
    deleted_applicant_ids: list[int] = Field(default_factory=list)
    deleted_count: int = Field(..., ge=0)
    deleted_screening_log_ids: list[int] = Field(default_factory=list)
    deleted_screening_log_count: int = Field(..., ge=0)
    deleted_welfare_request_consent_ids: list[int] = Field(default_factory=list)
    deleted_welfare_request_consent_count: int = Field(..., ge=0)
