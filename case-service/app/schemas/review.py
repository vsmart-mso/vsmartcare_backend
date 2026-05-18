"""Schemas สำหรับ review_field และ welfare_review_comment."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ReviewFieldRead(BaseModel):
    id: int
    name: str
    label: str
    step: int
    display_order: int

    model_config = ConfigDict(from_attributes=True)


class WelfareReviewCommentCreate(BaseModel):
    review_field_id: int = Field(..., ge=1)
    reason: str = Field(..., min_length=1)


class WelfareReviewCommentRead(BaseModel):
    id: int
    review_field_id: int
    reason: str

    model_config = ConfigDict(from_attributes=True)


class WelfareEditRequestCreate(BaseModel):
    applicant_id: int = Field(..., ge=1)
    update_by_sdshv: str | None = None
    remarks: str | None = None
    comments: list[WelfareReviewCommentCreate] = Field(..., min_length=1)


class WelfareEditRequestRead(BaseModel):
    welfare_request_status_id: int
    comments: list[WelfareReviewCommentRead]
