"""Pydantic schemas สำหรับ article."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ArticleBase(BaseModel):
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


class ArticleRead(ArticleBase):
    id: int
    applicant_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArticleCreate(ArticleBase):
    applicant_id: int = Field(..., ge=1)


class ArticleUpdate(ArticleBase):
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
