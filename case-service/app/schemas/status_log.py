"""Pydantic schemas สำหรับ welfare_request_status."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WelfareRequestStatusBase(BaseModel):
    applicant_id: int
    current_status_id: int
    updated_by_firstname: str | None = Field(None, max_length=255)
    updated_by_lastname: str | None = Field(None, max_length=255)
    remarks: str | None = None


class WelfareRequestStatusCreate(WelfareRequestStatusBase):
    pass


class WelfareRequestStatusRead(WelfareRequestStatusBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
