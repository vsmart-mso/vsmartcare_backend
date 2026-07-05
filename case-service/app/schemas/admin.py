"""Schemas สำหรับ admin API (TASK-v-care-12062026-01)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AdminLoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=255)


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="อายุ token (วินาที)")


class ProvinceAccessRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    province_id: int
    province_name: str
    is_enabled: bool
    updated_at: datetime | None = None


class ProvinceAccessUpdate(BaseModel):
    is_enabled: bool


class ProvinceAccessBulkResult(BaseModel):
    """ผลการตั้งค่าเปิด/ปิดทุกจังหวัดพร้อมกัน."""

    updated: int = Field(..., description="จำนวนจังหวัดที่ถูกตั้งค่า")
    is_enabled: bool


class RandomCasesCreateBody(BaseModel):
    """สร้างคำร้องสุ่ม (dev/staging) — person + applicant + ตารางย่อย."""

    count: int = Field(1, ge=1, le=50, description="จำนวนเคสที่ต้องการสร้าง")
    province_id: int | None = Field(
        None,
        ge=1,
        description="จำกัดจังหวัด (ว่าง = สุ่มทุกจังหวัด)",
    )


class RandomCaseCreatedRead(BaseModel):
    applicant_id: int
    case_number: str | None
    persons_id: int
    cid: str
    full_name: str
    province_id: int | None = None
    province_name: str | None = None


class RandomCasesCreateResult(BaseModel):
    created: int
    cases: list[RandomCaseCreatedRead]
