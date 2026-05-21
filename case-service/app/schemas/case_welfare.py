"""สคีมารวมสำหรับบันทึกคำร้อง (case) และหลักฐานเป็นขั้นตอนแยก (multipart).

ฟิลด์ `applicants.is_existing_case`, `is_emergency`, `time_count_process` ไม่รับจาก client
เมื่อสร้างคำร้อง — DB จะใช้ค่า default จากโมเดล
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .address import AddressRead
from .applicant import ApplicantRead
from .dependency import DependencyLoadRead
from .economic import EconomicInfoRead
from .status_log import WelfareRequestStatusRead
from .welfare import (
    WelfareEvidenceRead,
    WelfareHistoryRead,
    WelfareRequestTypeRead,
)


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


class EconomicInfoInCase(BaseModel):
    housing_types_id: int | None = None
    housing_types_rent: Decimal | None = None
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
        Field(
            min_length=1,
            description="รายการ id จาก request_types — สร้างแถวใน welfare_request_types",
        ),
    ]
    request_other_text: str | None = Field(
        None,
        max_length=500,
        description="ระบุรายละเอียดเมื่อเลือก request_type_id=3 (ช่วยเหลือเรื่องอื่นๆ)",
    )
    welfare_history: WelfareHistoryInCase | None = None
    initial_current_status_id: int = Field(
        1,
        description="FK current_status.id — เช่น 1 = รอรับเรื่อง",
    )


class WelfareApplicantUpdate(BaseModel):
    """ทุกฟิลด์ optional — ส่งเฉพาะสิ่งที่ต้องการเปลี่ยน (persons_id ห้ามเปลี่ยน)"""
    requester_relation_id: int | None = None
    marital_status_id: int | None = None
    mobile_phone: str | None = Field(default=None, max_length=20)
    home_phone: str | None = Field(default=None, max_length=20)
    fax_number: str | None = Field(default=None, max_length=20)
    email_address: EmailStr | None = None
    problem_details: str | None = None
    bank_name_id: int | None = Field(default=None, ge=1)
    bank_account_no: str | None = Field(default=None, max_length=50)
    age: int | None = Field(default=None, ge=0)
    # True → clear สถานะการดำเนินงาน: process_started_at, process_sla_days, type_money_category_id = NULL
    reset_processing_state: bool = False


class WelfareCaseUpdate(BaseModel):
    """Payload สำหรับ PATCH /v1/cases/{applicant_id}

    ส่งเฉพาะส่วนที่ต้องการแก้ไข — None = ไม่แตะ, list ใหม่ = replace ทั้ง section
    """
    applicant: WelfareApplicantUpdate | None = None
    addresses: list[AddressInCase] | None = None
    dependency_loads: list[DependencyLoadInCase] | None = None
    economic_infos: list[EconomicInfoInCase] | None = None
    request_type_ids: list[int] | None = None
    request_other_text: str | None = Field(
        None,
        max_length=500,
        description="ระบุรายละเอียดเมื่อเลือก request_type_id=3 (ช่วยเหลือเรื่องอื่นๆ)",
    )
    welfare_history: WelfareHistoryInCase | None = None


class WelfareCaseRead(BaseModel):
    """ผลหลังบันทึก / หลังดึงข้อมูลคำร้อง (applicant.id ใช้เป็นตัวอ้างอิงคำร้อง)"""

    applicant: ApplicantRead
    addresses: list[AddressRead]
    dependency_loads: list[DependencyLoadRead]
    economic_infos: list[EconomicInfoRead]
    welfare_request_types: list[WelfareRequestTypeRead]
    welfare_history: WelfareHistoryRead | None
    welfare_evidences: list[WelfareEvidenceRead]
    welfare_request_status_logs: list[WelfareRequestStatusRead]
    latest_welfare_request_status: WelfareRequestStatusRead | None = Field(
        None,
        description="สถานะปัจจุบัน (แถวล่าสุดจาก welfare_request_status)",
    )
    created_at: datetime | None = Field(
        None,
        description="เวลา created_at ของ applicant — ความสะดวกฝั่ง client",
    )
    count_037: int = Field(
        0,
        ge=0,
        description="จำนวน welfare_payment ที่ is_037_or_038 = false (ฟอร์ม 037)",
    )
    model_config = ConfigDict(from_attributes=True)


class WelfareEvidenceUploadRead(BaseModel):
    evidence: WelfareEvidenceRead
