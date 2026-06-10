"""โครงสร้าง body สำหรับ `POST /v1/cases` — ต้องสอดคล้องกับ case-service `app.schemas.case_welfare.WelfareCaseCreate`."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field

PhysicalCondition = Literal["normal", "disabled", "chronic_illness"]


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
    bank_account_type_id: int | None = Field(None, ge=1)   # ประเภทเงินฝาก (FK bank_account_type)
    bank_branch_name: str | None = Field(None, max_length=255)  # ชื่อสาขาจาก OCR
    type_money_category_id: int | None = Field(None, ge=1)
    sw_explorer_sdshv: str | None = Field(None, max_length=255)
    age: int | None = Field(None, ge=0)


class AddressInCase(BaseModel):
    sub_district_postcode_id: int
    address_type_id: int
    alley: str | None = Field(None, max_length=255)
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


class HouseholdMemberInCase(BaseModel):
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
    household_members: list[HouseholdMemberInCase] = Field(default_factory=list)
    request_type_ids: Annotated[
        list[int],
        Field(min_length=1),
    ]
    request_other_text: str | None = Field(None, max_length=500)
    request_in_kind_text: str | None = Field(None, max_length=500)
    welfare_history: WelfareHistoryInCase | None = None
    initial_current_status_id: int = Field(
        1,
        description="FK current_status.id — เช่น 1 = รอรับเรื่อง",
    )
