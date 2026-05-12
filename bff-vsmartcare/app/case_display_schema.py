"""สคีมาสรุปคำร้องสำหรับแสดงสถานะ — สอดคล้องกับ case-service `CaseDisplayRead`."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CurrentStatusDisplay(BaseModel):
    id: int
    description_public: str
    description_staff: str
    color: str
    dropdown_to_change: str
    dropdown_order: int
    dropdown_activate: bool = False
    filter_order: int
    filter_activate: bool = True


class CaseDisplayRead(BaseModel):
    applicant_id: int
    case_number: Optional[str] = Field(None, max_length=100)
    datetime_create: datetime
    time_count_process: Optional[int] = Field(None, ge=0)
    is_existing_case: bool
    current_status: Optional[CurrentStatusDisplay] = None
    description_public: Optional[str] = None
