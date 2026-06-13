"""Pydantic schemas สำหรับ case_data_edit_logs."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CaseDataEditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    applicant_id: int
    current_status_id_at_edit: int
    edit_by_sdshv: str | None = Field(None, max_length=255)
    event_type: str = Field(..., max_length=32)
    sections: list[int] = Field(default_factory=list)
    remarks: str | None = None

    @field_validator("sections", mode="before")
    @classmethod
    def _parse_sections(cls, value: object) -> list[int]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [int(v) for v in value]
        if isinstance(value, str):
            parts = [p.strip() for p in value.split(",") if p.strip()]
            return [int(p) for p in parts]
        return []


class CaseDataEditLogCreate(BaseModel):
    applicant_id: int = Field(..., ge=1)
    event_type: str = Field(..., max_length=32)
    sections: list[int] | None = Field(
        None,
        description="section ปสค.1 ที่แก้ — เช่น [2, 4] สำหรับ event_type=section_edit",
    )
    remarks: str | None = Field(None, max_length=2000)
    edit_by_sdshv: str | None = Field(None, max_length=255)
