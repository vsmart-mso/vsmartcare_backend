"""Pydantic schemas for cover_document_batch."""

from __future__ import annotations

from datetime import date, datetime

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

    model_config = ConfigDict(from_attributes=True)


class CoverDocumentBatchListResponse(BaseModel):
    items: list[CoverDocumentBatchRead]
