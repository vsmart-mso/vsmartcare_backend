"""Pydantic schemas สำหรับ OCR Pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MatchStatus(str, Enum):
    match = "match"
    review = "review"
    mismatch = "mismatch"
    blurry = "blurry"
    no_text = "no_text"


class BankInfo(BaseModel):
    account_number: str | None = Field(None, description="หมายเลขบัญชีที่ OCR อ่านได้")
    account_name: str | None = Field(None, description="ชื่อบัญชีที่ OCR อ่านได้")
    bank_name: str | None = Field(None, description="ชื่อธนาคารที่ OCR อ่านได้")
    match_status: MatchStatus = Field(..., description="สถานะการจับคู่เทียบกับชื่อเป้าหมาย")
    fuzzy_score: float = Field(0.0, description="คะแนน fuzzy match 0-100")


class OcrResponse(BaseModel):
    id: int = Field(..., description="ID ของผล OCR ใน DB — ใช้สำหรับ PATCH link ทีหลัง")
    markdown: str = Field("", description="ข้อความเต็มจาก OCR ในรูปแบบ Markdown")
    bank_info: BankInfo | None = Field(None, description="ข้อมูลบัญชีธนาคารที่สกัดได้")
    target_name_checked: str = Field("", description="ชื่อเป้าหมายที่ใช้ในการตรวจสอบ")
    pre_file: str = Field("", description="uuid ของไฟล์ต้นฉบับที่อัปโหลด")


# ── DB read schemas ─────────────────────────────────────────────

class OcrResultRead(BaseModel):
    """อ่านผล OCR ที่บันทึกใน DB."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    applicant_id: int | None = None
    target_name_checked: str
    pre_file: str
    markdown: str
    account_number: str | None = None
    account_name: str | None = None
    bank_name: str | None = None
    match_status: MatchStatus
    fuzzy_score: float
    created_at: datetime
    updated_at: datetime


class OcrResultListResponse(BaseModel):
    applicant_id: int | None = None
    results: list[OcrResultRead]
    count: int
