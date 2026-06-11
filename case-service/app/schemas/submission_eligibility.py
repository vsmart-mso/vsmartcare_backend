"""สคีมาตอบกลับการตรวจสอบสิทธิ์ยื่นคำขอของประชาชน."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EligibilityReason = Literal["none", "active_case", "cooldown", "eligible", "unknown_status"]


class SubmissionEligibilityRead(BaseModel):
    can_submit: bool = Field(..., description="ยื่นคำขอใหม่ได้หรือไม่")
    can_access_portal: bool = Field(..., description="เข้าใช้งานระบบได้หรือไม่ (ปัจจุบันเป็น true เสมอ — ดูสถานะได้แม้ช่วง cooldown)")
    reason: EligibilityReason
    last_applicant_id: int | None = None
    last_submitted_at: datetime | None = None
    eligible_at: datetime | None = None
    days_remaining: int | None = Field(None, ge=0, description="จำนวนวันที่เหลือก่อนยื่นได้ (ปัดขึ้น)")
    current_status_id: int | None = None
