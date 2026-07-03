"""สคีมาผลตรวจสอบรายใหม่ / รายเดิมจากเลขบัตรประชาชน.

ใช้คู่กับ ``app.api.check_case.check_existing_case_by_cid`` และ
``GET /v1/check-case`` — ดูวิธีใช้และตัวอย่าง response ใน module docstring ของ ``check_case.py``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CheckCaseSource = Literal["vcare_main", "mso_logbook", "vsmart_main"]


class SourceCheckResult(BaseModel):
    source: CheckCaseSource
    found: bool = Field(description="พบข้อมูลในระบบนี้หรือไม่ (เมื่อ available=true)")
    available: bool = Field(
        description="ตรวจสอบได้สำเร็จหรือไม่ (false = ไม่ได้ตั้งค่า URL หรือเรียก API ไม่สำเร็จ)",
    )
    message: str | None = None
    detail: dict[str, Any] | None = None


class ExistingCaseCheckResult(BaseModel):
    cid: str = Field(..., min_length=13, max_length=13)
    is_existing_case: bool = Field(
        description="รายเดิม ถ้าพบในอย่างน้อยหนึ่งแหล่งที่ตรวจสอบได้",
    )
    sources: list[SourceCheckResult]
