"""โครงสร้าง body สำหรับ `POST /v1/cases` — ต้องสอดคล้องกับ case-service `app.schemas.case_welfare.WelfareCaseCreate`."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, EmailStr, Field


class WelfareApplicantUpsert(BaseModel):
    persons_id: int
    requester_relation_id: int
    marital_status_id: int
    mobile_phone: str | None = Field(None, max_length=20)
    home_phone: str | None = Field(None, max_length=20)
    fax_number: str | None = Field(None, max_length=20)
    email_address: EmailStr | None = None
    problem_details: str | None = None
    bank_name_id: int | None = Field(None, ge=1)
    bank_account_no: str | None = Field(None, max_length=50)
    age: int | None = Field(None, ge=0)


class AddressInCase(BaseModel):
    sub_district_postcode_id: int
    address_type_id: int
    sub_lane: str | None = Field(None, max_length=255)
    house_name: str | None = Field(None, max_length=255)
    road: str | None = Field(None, max_length=255)
    house_moo: str | None = Field(None, max_length=50)
    house_number: str | None = Field(None, max_length=50)
    mobile_phone: str | None = Field(None, max_length=20)
    latitude: str | None = Field(None, max_length=50)
    longitude: str | None = Field(None, max_length=50)


class DependencyLoadInCase(BaseModel):
    dependency_type_id: int
    dependency_other_text: str | None = Field(None, max_length=500)


class EconomicIncomeSourceInCase(BaseModel):
    income_source_type_id: int
    other_details: str | None = Field(None, max_length=500)


class EconomicInfoInCase(BaseModel):
    housing_types_id: int | None = None
    occupation: str | None = Field(None, max_length=255)
    monthly_income: Decimal | None = None
    household_members: int | None = Field(None, ge=0)
    family_occupation: str | None = Field(None, max_length=255)
    income_sources: list[EconomicIncomeSourceInCase] = Field(default_factory=list)


class WelfareHistoryDetailInCase(BaseModel):
    received_welfare_type_id: int
    received_other: str | None = Field(None, max_length=500)


class WelfareHistoryInCase(BaseModel):
    received_count: int | None = Field(None, ge=0)
    has_received_welfare: bool = False
    total_received_amount: Decimal | None = None
    history_details: list[WelfareHistoryDetailInCase] = Field(default_factory=list)


class WelfareCaseCreate(BaseModel):
    applicant: WelfareApplicantUpsert
    addresses: list[AddressInCase] = Field(default_factory=list)
    dependency_loads: list[DependencyLoadInCase] = Field(default_factory=list)
    economic_infos: list[EconomicInfoInCase] = Field(default_factory=list)
    request_type_ids: Annotated[
        list[int],
        Field(min_length=1),
    ]
    welfare_history: WelfareHistoryInCase | None = None
    initial_current_status_id: int = Field(
        1,
        description="FK current_status.id — เช่น 1 = รอรับเรื่อง",
    )
