"""Pydantic schemas สำหรับ payment intake flow — หน้า 11, 13, 20 (v2)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from ..models.intake import KtbNotifyChannel, KtbRecipientCategory
from .lookup import BankAccountTypeRead, TypeMoneyRead


# ---------------------------------------------------------------------------
# AnnouncementRegulation (master dropdown หน้า 11)
# ---------------------------------------------------------------------------


class RegulationRead(BaseModel):
    """แถวระเบียบ/ประกาศ แบบ flat สำหรับ admin."""

    id: int
    code: str
    name: str
    short_name: str | None = None
    type_money_category_id: int
    maximum_money: Decimal
    limit_per_budget_year: int
    sort_order: int | None = None
    activate: bool

    model_config = ConfigDict(from_attributes=True)


class RegulationDropdownItem(BaseModel):
    """แถวระเบียบในรูปแบบ dropdown หน้า 11 — รวม count_used / disabled."""

    id: int
    code: str
    name: str
    display_name: str = Field(description="(short_name) name สำหรับแสดงผล")
    type_money_category_id: int
    type_money_category_name_acronym: str = Field(description="ชื่อย่อหมวดเงิน เช่น ฉก.")
    maximum_money: Decimal
    limit_per_budget_year: int
    activate: bool
    count_used: int = Field(default=0, description="ครั้งที่บุคคลนี้ใช้ระเบียบนี้ในปีงบประมาณ")
    disabled: bool = Field(default=False, description="True เมื่อ count_used >= limit_per_budget_year")

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# PaymentMethod (master dropdown หน้า 13)
# ---------------------------------------------------------------------------


class PaymentMethodRead(BaseModel):
    id: int
    code: str
    name_th: str
    legacy_vsmart_value: str | None = None
    sort_order: int
    requires_ktb_form: bool

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# CaseHandling + CaseRegulationChoice (หน้า 11)
# ---------------------------------------------------------------------------


class HelpBeneficiaryUpsert(BaseModel):
    """ผู้รับความช่วยเหลือที่เลือก — null household_member_id = ผู้ยื่น."""

    household_member_id: int | None = None
    display_name: str | None = Field(None, max_length=255)
    national_id: str | None = Field(None, max_length=13)
    age_years: int | None = None


class HelpBeneficiaryRead(BaseModel):
    id: int
    household_member_id: int | None = None
    display_name: str | None = None
    national_id: str | None = None
    age_years: int | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IntakeHandlingUpsert(BaseModel):
    """Body สำหรับ POST/PATCH /cases/{id}/intake — บันทึกข้อมูลหน้า 11."""

    vsmart_informer_id: int | None = None
    vsmart_social_worker_id: int | None = None
    sw_user_sdshv: str | None = Field(None, max_length=255)
    type_money_id: int | None = Field(None, description="id จาก type_money")
    regulation_id: int = Field(..., description="id จาก announcement_regulations")
    help_kind: str = Field(default="money", description="money | things")
    money_amount: Decimal | None = Field(None, ge=0)
    comment: str | None = None
    esignature: str | None = None
    signed_by_sdshv: str | None = Field(None, max_length=255)
    selected_beneficiaries: list[HelpBeneficiaryUpsert] | None = Field(
        None,
        description="None = ไม่แตะตารางเดิม; list (รวมว่าง) = แทนที่ทั้งชุด",
    )


class RegulationChoiceRead(BaseModel):
    id: int
    case_handling_id: int
    regulation_id: int
    help_kind: str
    money_amount: Decimal | None = None
    comment: str | None = None
    esignature: str | None = None
    signed_by_sdshv: str | None = None
    created_at: datetime
    updated_at: datetime

    regulation: RegulationRead | None = None

    model_config = ConfigDict(from_attributes=True)


class CaseHandlingRead(BaseModel):
    id: int
    applicant_id: int
    vsmart_informer_id: int | None = None
    vsmart_social_worker_id: int | None = None
    sw_user_sdshv: str | None = None
    type_money_id: int | None = None
    intake_completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    regulation_choice: RegulationChoiceRead | None = None
    type_money: TypeMoneyRead | None = None
    help_beneficiaries: list[HelpBeneficiaryRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# CasePayment (หน้า 13)
# ---------------------------------------------------------------------------


class CasePaymentUpsert(BaseModel):
    """Body สำหรับ POST/PATCH /cases/{id}/intake/payment — บันทึกวิธีจ่ายเงินหน้า 13."""

    payment_method_id: int
    receive_mode: str | None = Field(None, description="self | agent")
    agent_person_id: int | None = None
    payee_person_id: int | None = None
    bank_name_id: int | None = None
    bank_branch: str | None = Field(None, max_length=255)
    bank_account_type_id: int | None = None
    account_number: str | None = Field(None, max_length=50)
    account_name: str | None = Field(None, max_length=255)
    cheque_reference: str | None = Field(None, max_length=100)


class CasePaymentRead(BaseModel):
    id: int
    case_handling_id: int
    payment_method_id: int
    receive_mode: str | None = None
    agent_person_id: int | None = None
    payee_person_id: int | None = None
    bank_name_id: int | None = None
    bank_branch: str | None = None
    bank_account_type_id: int | None = None
    account_number: str | None = None
    account_name: str | None = None
    cheque_reference: str | None = None
    created_at: datetime
    updated_at: datetime

    payment_method: PaymentMethodRead | None = None
    bank_account_type: BankAccountTypeRead | None = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# CaseKtbCorporate (หน้า 20)
# ---------------------------------------------------------------------------


class CaseKtbCorporateUpsert(BaseModel):
    """Body สำหรับ POST/PATCH /cases/{id}/intake/ktb — บันทึกข้อมูล KTB Corporate หน้า 20."""

    form_number: int | None = None
    director_division_ref: str | None = Field(None, max_length=500)
    paying_division_ref: str | None = Field(None, max_length=500)
    recipient_category: KtbRecipientCategory
    payroll_bank_name_id: int | None = None
    payroll_bank_branch: str | None = Field(None, max_length=255)
    payroll_account_type: str | None = Field(None, max_length=100)
    payroll_account_number: str | None = Field(None, max_length=50)
    other_bank_name_id: int | None = None
    other_bank_branch: str | None = Field(None, max_length=255)
    other_account_type: str | None = Field(None, max_length=100)
    other_account_number: str | None = Field(None, max_length=50)
    notify_channel: KtbNotifyChannel | None = None
    notify_contact: str | None = Field(None, max_length=255)


class CaseKtbCorporateRead(BaseModel):
    id: int
    case_handling_id: int
    form_number: int | None = None
    director_division_ref: str | None = None
    paying_division_ref: str | None = None
    recipient_category: KtbRecipientCategory
    payroll_bank_name_id: int | None = None
    payroll_bank_branch: str | None = None
    payroll_account_type: str | None = None
    payroll_account_number: str | None = None
    other_bank_name_id: int | None = None
    other_bank_branch: str | None = None
    other_account_type: str | None = None
    other_account_number: str | None = None
    notify_channel: KtbNotifyChannel | None = None
    notify_contact: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# CaseDiagnosis — คำวินิจฉัยหลายรายการ (BR-DIAG-01..06)
# ---------------------------------------------------------------------------


class CaseDiagnosisCreate(BaseModel):
    """Body สำหรับ POST /cases/{id}/diagnoses — เพิ่มคำวินิจฉัยของ user ตนเอง."""

    diagnosis_text: str = Field(..., min_length=1)
    owner_user_id: int = Field(..., gt=0, description="Django user id ฝั่ง VSmart")
    owner_sdshv: str | None = Field(None, max_length=255)
    owner_name: str | None = Field(None, max_length=255)
    owner_position: str | None = Field(None, max_length=255)
    owner_organization: str | None = Field(None, max_length=255)


class CaseDiagnosisUpdate(BaseModel):
    """Body สำหรับ PATCH /cases/{id}/diagnoses/{diagnosis_id} — แก้ได้เฉพาะของตนเอง."""

    diagnosis_text: str = Field(..., min_length=1)
    actor_user_id: int = Field(..., gt=0, description="user ผู้ขอแก้ — ต้องตรง owner_user_id")
    actor_name: str | None = Field(None, max_length=255)
    edit_reason: str | None = None
    # snapshot ใหม่ (ตำแหน่ง/หน่วยงานอาจเปลี่ยน) — optional, อัปเดตเมื่อส่งมา
    owner_position: str | None = Field(None, max_length=255)
    owner_organization: str | None = Field(None, max_length=255)


class CaseDiagnosisEditHistoryRead(BaseModel):
    id: int
    diagnosis_id: int
    old_text: str
    new_text: str
    edit_reason: str | None = None
    edited_by_user_id: int
    edited_by_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseDiagnosisRead(BaseModel):
    id: int
    applicant_id: int
    diagnosis_text: str
    owner_user_id: int
    owner_sdshv: str | None = None
    owner_name: str | None = None
    owner_position: str | None = None
    owner_organization: str | None = None
    created_at: datetime
    updated_at: datetime
    is_owner: bool = Field(default=False, description="True เมื่อ actor_user_id ตรง owner")
    edit_count: int = Field(default=0, description="จำนวนครั้งที่แก้ไข")

    model_config = ConfigDict(from_attributes=True)


class CaseDiagnosisDetailRead(CaseDiagnosisRead):
    edit_histories: list[CaseDiagnosisEditHistoryRead] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# CaseIntakeRead — สถานะ intake ทั้งหมดของ applicant
# ---------------------------------------------------------------------------


class CaseIntakeRead(BaseModel):
    """สถานะ intake ทั้งหมดของ applicant — ใช้สำหรับ GET /cases/{id}/intake."""

    applicant_id: int
    case_handling: CaseHandlingRead | None = None
    payment: CasePaymentRead | None = None
    ktb_corporate: CaseKtbCorporateRead | None = None
    intake_completed: bool = Field(
        default=False,
        description="True เมื่อ case_handling.intake_completed_at มีค่า",
    )

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Latest helped case by CID — GET /v1/intake/latest-helped-case
# ---------------------------------------------------------------------------


class LatestHelpedCasePerson(BaseModel):
    """ข้อมูลผู้ประสบปัญหาสำหรับเติมฟอร์ม Smart."""

    citizen_id: str = Field(..., min_length=13, max_length=13)
    prefix: str | None = None
    first_name: str
    last_name: str
    birthdate: date | None = None
    gender: str | None = None
    phone: str | None = None
    home_phone: str | None = None
    email: str | None = None
    education: str | None = None
    ethnicity: str | None = None
    nationality: str | None = None
    religion: str | None = None
    marital_status_id: int | None = Field(None, description="id จาก marital_status_types")
    marital_status: str | None = Field(None, description="สถานภาพสมรส")


class LatestHelpedCaseAddress(BaseModel):
    """ที่อยู่ทะเบียนบ้าน / ปัจจุบัน — ว่างได้เป็น {}."""

    house_no: str | None = None
    moo: str | None = None
    village: str | None = None
    lane: str | None = None
    alley: str | None = None
    road: str | None = None
    province: str | None = Field(None, description="รหัสจังหวัด (code หรือ fallback id)")
    district: str | None = Field(None, description="รหัสอำเภอ (code หรือ fallback id)")
    sub_district: str | None = Field(None, description="รหัสตำบล (code หรือ fallback id)")
    province_name: str | None = None
    district_name: str | None = None
    sub_district_name: str | None = None
    postcode: str | None = None


class LatestHelpedCaseHousing(BaseModel):
    """สภาพที่อยู่อาศัย จาก economic_infos."""

    id: int | None = Field(None, description="housing_types_id")
    name: str | None = Field(None, description="ชื่อประเภทที่อยู่อาศัยจาก master")
    shelter: str | None = Field(None, description="ข้อความสภาพที่อยู่อาศัย (housing_shelter)")


class LatestHelpedCaseFamilyOccupation(BaseModel):
    """อาชีพหลักของครอบครัว จาก economic_infos."""

    id: int | None = Field(None, description="family_occupation_type_id")
    name: str | None = Field(None, description="ชื่ออาชีพจาก master occupation_types")
    detail: str | None = Field(None, description="ข้อความอาชีพเพิ่มเติม (family_occupation)")


class LatestHelpedCaseIncomeSource(BaseModel):
    """ที่มาของรายได้หนึ่งรายการ จาก economic_income_sources."""

    id: int = Field(..., description="income_source_type_id")
    name: str | None = Field(None, description="ชื่อจาก income_source_types")
    other_details: str | None = Field(None, description="รายละเอียดเมื่อเลือกอื่น ๆ")


class LatestHelpedCaseDependency(BaseModel):
    """การอุปการะหนึ่งรายการ จาก dependency_loads."""

    id: int = Field(..., description="dependency_type_id")
    name: str | None = Field(None, description="ชื่อจาก dependency_types")
    other_text: str | None = Field(None, description="รายละเอียดเมื่อเลือกอื่น ๆ")


class LatestHelpedCaseResponse(BaseModel):
    """เคสช่วยเหลือล่าสุดตาม CID — found=false ส่งแค่ found."""

    found: bool
    helped_at: datetime | None = None
    applicant_id: int | None = None
    person: LatestHelpedCasePerson | None = None
    registered_address: LatestHelpedCaseAddress | None = None
    present_address: LatestHelpedCaseAddress | None = None
    housing: LatestHelpedCaseHousing | None = None
    family_occupation: LatestHelpedCaseFamilyOccupation | None = None
    monthly_income: Decimal | None = Field(
        None, description="รายได้เฉลี่ยต่อเดือนของครอบครัว (บาท)"
    )
    income_sources: list[LatestHelpedCaseIncomeSource] | None = Field(
        None, description="ที่มาของรายได้"
    )
    dependencies: list[LatestHelpedCaseDependency] | None = Field(
        None, description="การอุปการะ / ภาระเลี้ยงดู"
    )
