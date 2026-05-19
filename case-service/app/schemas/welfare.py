"""Pydantic schemas สำหรับสวัสดิการ (welfare_*)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class WelfareHistoryDetailBase(BaseModel):
    welfare_history_id: int
    received_welfare_type_id: int
    received_other: str | None = Field(None, max_length=500)


class WelfareHistoryDetailCreate(WelfareHistoryDetailBase):
    pass


class WelfareHistoryDetailRead(WelfareHistoryDetailBase):
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WelfareHistoryBase(BaseModel):
    applicant_id: int
    received_count: int | None = Field(None, ge=0)
    has_received_welfare: bool = False
    total_received_amount: Decimal | None = None


class WelfareHistoryCreate(WelfareHistoryBase):
    pass


class WelfareHistoryRead(WelfareHistoryBase):
    history_details: list[WelfareHistoryDetailRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WelfareRequestTypeBase(BaseModel):
    applicant_id: int
    request_type_id: int
    request_other_text: str | None = Field(None, max_length=500)


class WelfareRequestTypeCreate(WelfareRequestTypeBase):
    pass


class WelfareRequestTypeRead(WelfareRequestTypeBase):
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class WelfareEvidenceBase(BaseModel):
    attachment_type_id: int
    applicant_id: int
    file_path: str = Field(..., max_length=1024)
    file_original_name: str | None = Field(None, max_length=255)
    file_stored_name: str | None = Field(None, max_length=255)
    file_size: int | None = Field(None, ge=0)
    file_width: int | None = Field(None, ge=0)
    file_height: int | None = Field(None, ge=0)
    file_other_type_name: str | None = Field(None, max_length=255)


class WelfareEvidenceCreate(WelfareEvidenceBase):
    pass


class WelfareEvidenceRead(WelfareEvidenceBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
