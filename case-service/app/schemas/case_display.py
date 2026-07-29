"""สคีมาสรุปคำร้องสำหรับแสดงสถานะบนหน้า client."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ..utils.datetime_th import to_bangkok
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

    # ส่งออกเป็นเวลาไทย (aware, offset +07:00) — ค่าใน DB เป็น UTC naive จาก func.now()
    @field_serializer("datetime_create")
    def _serialize_datetime_create(self, value: datetime) -> str:
        return to_bangkok(value).isoformat()
