"""สคีมาสรุปคำร้องสำหรับแสดงสถานะบนหน้า client."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .lookup import CurrentStatusRead
from .process_sla import ProcessSlaFields


class CaseDisplayRead(ProcessSlaFields):
    applicant_id: int
    case_number: str | None = Field(None, max_length=100)
    datetime_create: datetime
    time_count_process: int | None = Field(None, ge=0)
    is_existing_case: bool
    current_status: CurrentStatusRead | None = None
    description_public: str | None = None
    model_config = ConfigDict(from_attributes=True)
