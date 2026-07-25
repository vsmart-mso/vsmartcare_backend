"""Schemas สำหรับ review_field และ welfare_review_comment."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CitizenConfirmationType = Literal["unchanged_ok", "edited"]


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


class WelfareReviewCommentWithFieldRead(BaseModel):
    id: int
    reason: str
    review_field: ReviewFieldRead | None = None

    model_config = ConfigDict(from_attributes=True)


class WelfareEditRequestCreate(BaseModel):
    applicant_id: int = Field(..., ge=1)
    update_by_sdshv: str | None = None
    remarks: str | None = None
    comments: list[WelfareReviewCommentCreate] = Field(..., min_length=1)


class WelfareEditRequestRead(BaseModel):
    welfare_request_status_id: int
    comments: list[WelfareReviewCommentRead]


class WelfareEditRequestCommentRead(BaseModel):
    """comment ต่อ field จากการส่งกลับแก้ไข (status=8) — สำหรับฝั่งประชาชน."""

    review_field_id: int
    name: str
    label: str
    step: int
    reason: str


class FieldConfirmationItem(BaseModel):
    """การยืนยันต่อฟิลด์จากประชาชนตอน resubmit (TASK_211)."""

    review_field_id: int = Field(..., ge=1)
    confirmation_type: CitizenConfirmationType


class WelfareCaseResubmitBody(BaseModel):
    """Body ของ POST /v1/cases/{id}/resubmit เมื่อสถานะเป็น 8."""

    field_confirmations: list[FieldConfirmationItem] = Field(..., min_length=1)
