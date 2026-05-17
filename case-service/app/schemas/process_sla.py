"""ฟิลด์ SLA กระบวนการ — คำนวณตอนอ่าน + ค่าจาก DB."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ProcessTrafficColor = Literal["green", "yellow", "orange", "red"]


class ProcessSlaFields(BaseModel):
    process_started_at: datetime | None = None
    process_sla_days: int | None = Field(None, ge=1)
    process_elapsed_days: int | None = Field(None, ge=0)
    process_remaining_days: int | None = None
    process_traffic_color: ProcessTrafficColor | None = None
    process_is_overdue: bool | None = None
