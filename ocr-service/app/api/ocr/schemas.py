"""Pydantic schemas for OCR pipeline."""

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
    account_number: str | None = Field(None, description="OCR extracted account number")
    account_name: str | None = Field(None, description="OCR extracted account holder name")
    bank_name: str | None = Field(None, description="OCR extracted bank name")
    deposit_type: str | None = Field(None, description="OCR extracted deposit type")
    branch_name: str | None = Field(None, description="OCR extracted branch name")
    branch_code: str | None = Field(None, description="OCR extracted branch code")
    match_status: MatchStatus = Field(..., description="Name matching status")
    fuzzy_score: float = Field(0.0, description="Fuzzy match score 0-100")


class OcrResponse(BaseModel):
    id: int = Field(..., description="OCR result ID in DB")
    markdown: str = Field("", description="Full OCR text in markdown format")
    bank_info: BankInfo | None = Field(None, description="Extracted bank account information")
    target_name_checked: str = Field("", description="Target name used for matching")
    pre_file: str = Field("", description="Uploaded file UUID")


class OcrResultRead(BaseModel):
    """Read OCR result record from DB."""

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