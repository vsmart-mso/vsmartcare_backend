"""Pydantic schemas สำหรับ dependency_loads."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DependencyLoadBase(BaseModel):
    applicant_id: int
    dependency_type_id: int
    dependency_other_text: str | None = Field(None, max_length=500)


class DependencyLoadCreate(DependencyLoadBase):
    pass


class DependencyLoadRead(DependencyLoadBase):
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
