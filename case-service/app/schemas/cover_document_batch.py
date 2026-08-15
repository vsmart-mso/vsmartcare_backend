"""Pydantic schemas for cover_document_batch."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class CoverDocumentBatchBase(BaseModel):
    service_vsmart_id: str | None = Field(None, max_length=255)
    phone_service: str | None = Field(None, max_length=255)
    at: str | None = Field(None, max_length=255)
    date_at: date | None = None
    title: str | None = Field(None, max_length=255)
    director_vsmart_id: str | None = Field(
        None,
        max_length=255,
        validation_alias=AliasChoices("director_vsmart_id", "refer_vsmart_id"),
    )
    original_story: str | None = None
    fact_story: str | None = None
    laws: str | None = None
    consider: str | None = None
    suggestion: str | None = None
    type_money_id: int | None = None
    province_id: int | None = None
    approver_sdhsv: str | None = Field(None, max_length=64)


class CoverDocumentBatchCreate(CoverDocumentBatchBase):
    applicant_ids: list[int] = Field(..., min_length=1, max_length=30)


class CoverDocumentBatchUpdate(CoverDocumentBatchBase):
    pass


class CoverDocumentBatchRead(CoverDocumentBatchBase):
    id: int
    applicant_ids: list[int] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    # Optional enrichment when pending counts are computed (BC list)
    pending_count: int | None = None
    approved_count: int | None = None
    rejected_count: int | None = None
    pending_applicant_ids: list[int] | None = None
    approved_applicant_ids: list[int] | None = None
    all_applicant_ids: list[int] | None = None
    mode: Literal["batch"] = "batch"

    model_config = ConfigDict(from_attributes=True)


class CoverDocumentByDocumentRead(BaseModel):
    """One document set = (date_at, type_money_id) within province scope."""

    date_at: date
    type_money_id: int | None = None
    province_id: int | None = None
    at: str | None = None
    pending_count: int = 0
    approved_count: int = 0
    rejected_count: int = 0
    applicant_ids: list[int] = Field(default_factory=list)
    pending_applicant_ids: list[int] = Field(default_factory=list)
    approved_applicant_ids: list[int] = Field(default_factory=list)
    all_applicant_ids: list[int] = Field(default_factory=list)
    batch_ids: list[int] = Field(default_factory=list)
    mode: Literal["document"] = "document"


class CoverDocumentBatchListResponse(BaseModel):
    items: list[CoverDocumentBatchRead | CoverDocumentByDocumentRead]
    by_document: bool = False


class CoverDocumentMemberRead(BaseModel):
    applicant_id: int
    type_money_id: int | None = None
    case_number: str | None = None
    applicant_name: str | None = None
    is_approved: bool = False
    is_pmj_rejected: bool = False
    exists: bool = True
    province_id: int | None = None
    cid: str | None = None


class CoverDocumentMembersResponse(BaseModel):
    date_at: date
    type_money_id: int
    province_id: int | None = None
    items: list[CoverDocumentMemberRead] = Field(default_factory=list)
