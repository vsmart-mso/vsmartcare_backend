"""Pydantic schemas สำหรับ economic_infos และ economic_income_sources."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class EconomicIncomeSourceBase(BaseModel):
    income_source_type_id: int
    other_details: str | None = Field(None, max_length=500)


class EconomicIncomeSourceCreate(EconomicIncomeSourceBase):
    pass


class EconomicIncomeSourceRead(EconomicIncomeSourceBase):
    economic_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class EconomicInfoBase(BaseModel):
    applicant_id: int
    housing_types_id: int | None = None
    housing_types_rent: Decimal | None = None

    occupation: str | None = Field(None, max_length=255)
    monthly_income: Decimal | None = None
    household_members: int | None = Field(None, ge=0)
    family_occupation: str | None = Field(None, max_length=255)


class EconomicInfoCreate(EconomicInfoBase):
    income_sources: list[EconomicIncomeSourceCreate] = Field(default_factory=list)


class EconomicInfoUpdate(BaseModel):
    housing_types_id: int | None = None
    housing_types_rent: Decimal | None = None
    occupation: str | None = Field(None, max_length=255)
    monthly_income: Decimal | None = None
    household_members: int | None = Field(None, ge=0)
    family_occupation: str | None = Field(None, max_length=255)


class EconomicInfoRead(EconomicInfoBase):
    id: int
    income_sources: list[EconomicIncomeSourceRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
