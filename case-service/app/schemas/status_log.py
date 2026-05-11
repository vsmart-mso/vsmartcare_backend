"""Pydantic schemas สำหรับ welfare_request_status."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .lookup import CurrentStatusRead


class WelfareRequestStatusBase(BaseModel):
    applicant_id: int
    current_status_id: int
    update_by_sdshv: str | None = Field(None, max_length=255)
    remarks: str | None = None


class WelfareRequestStatusCreate(WelfareRequestStatusBase):
    pass


class WelfareRequestStatusRead(WelfareRequestStatusBase):
    id: int
    created_at: datetime
    updated_at: datetime
    current_status: CurrentStatusRead | None = None
    model_config = ConfigDict(from_attributes=True)
