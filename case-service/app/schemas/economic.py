"""Pydantic schemas สำหรับ economic_infos, economic_income_sources และ household_members."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PhysicalCondition = Literal["normal", "disabled", "chronic_illness"]


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


class HouseholdMemberBase(BaseModel):
    seq: int = Field(..., ge=1)
    national_id: str | None = Field(None, max_length=13)
    prefix_id: int | None = None
    prefix_other: str | None = Field(None, max_length=50)
    first_name: str = Field(..., max_length=255)
    last_name: str = Field(..., max_length=255)
    date_of_birth: date | None = None
    relation_to_applicant_id: int | None = None
    occupation: str | None = Field(None, max_length=255)
    monthly_income: Decimal | None = None
    physical_condition: PhysicalCondition = "normal"
    self_care: bool = True


class HouseholdMemberCreate(HouseholdMemberBase):
    applicant_id: int


class HouseholdMemberRead(HouseholdMemberBase):
    id: int
    applicant_id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
