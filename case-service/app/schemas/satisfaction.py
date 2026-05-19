"""Pydantic schemas สำหรับ satisfaction_surveys."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SurveyType = Literal["system_usage", "aid_received"]


class SatisfactionSurveyCreate(BaseModel):
    applicant_id: int = Field(..., ge=1)
    survey_type: SurveyType
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


class SatisfactionSurveyRead(BaseModel):
    id: int
    applicant_id: int
    survey_type: str
    rating: int
    comment: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
