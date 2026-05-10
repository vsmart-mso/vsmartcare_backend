"""Pydantic schemas สำหรับ screening_logs และ welfare_request_consents."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScreeningLogBase(BaseModel):
    person_id: int
    criteria_version: str | None = Field(None, max_length=50)
    screening_result: str | None = Field(None, max_length=100)
    failure_reason_code: str | None = Field(None, max_length=100)
    screening_status: bool = False
    input_data_snapshot: dict[str, Any] | None = None
    ip_address: str | None = Field(None, max_length=45)
    user_agent: str | None = Field(None, max_length=500)


class ScreeningLogCreate(ScreeningLogBase):
    pass


class ScreeningLogRead(ScreeningLogBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WelfareRequestConsentBase(BaseModel):
    person_id: int
    consent_type: str | None = Field(None, max_length=100)
    initial_pdpa_accepted: bool = False
    initial_terms_accepted: bool = False
    initial_warning_accepted: bool = False
    final_data_correct_accepted: bool = False


class WelfareRequestConsentCreate(WelfareRequestConsentBase):
    pass


class WelfareRequestConsentRead(WelfareRequestConsentBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
