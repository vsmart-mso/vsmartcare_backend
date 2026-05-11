"""Pydantic schemas สำหรับ applicants (ผู้ขอรับสวัสดิการ).

ข้อมูลชื่อ/เลขบัตรอยู่ที่ Person — ใช้ persons_id อ้างอิง
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ApplicantBase(BaseModel):
    persons_id: int
    case_number: str | None = Field(None, max_length=100)
    requester_relation_id: int
    marital_status_id: int

    mobile_phone: str | None = Field(None, max_length=20)
    home_phone: str | None = Field(None, max_length=20)
    fax_number: str | None = Field(None, max_length=20)
    email_address: EmailStr | None = None

    is_government_officer: bool = False

    problem_details: str | None = None

    bank_account_name: str | None = Field(None, max_length=255)
    bank_account_no: str | None = Field(None, max_length=50)

    time_count_process: int | None = Field(None, ge=0)

    is_emergency: bool = False
    is_existing_case: bool = False

    age: int | None = Field(None, ge=0)


class ApplicantCreate(ApplicantBase):
    pass


class ApplicantUpdate(BaseModel):
    persons_id: int | None = None
    case_number: str | None = Field(None, max_length=100)
    requester_relation_id: int | None = None
    marital_status_id: int | None = None
    mobile_phone: str | None = Field(None, max_length=20)
    home_phone: str | None = Field(None, max_length=20)
    fax_number: str | None = Field(None, max_length=20)
    email_address: EmailStr | None = None
    is_government_officer: bool | None = None
    bank_account_name: str | None = Field(None, max_length=255)
    bank_account_no: str | None = Field(None, max_length=50)
    time_count_process: int | None = Field(None, ge=0)
    is_emergency: bool | None = None
    is_existing_case: bool | None = None
    problem_details: str | None = None
    age: int | None = Field(None, ge=0)


class ApplicantRead(ApplicantBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
