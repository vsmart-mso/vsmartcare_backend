"""Pydantic schemas สำหรับ payment intake flow — หน้า 11, 13, 20 (v2)."""

from __future__ import annotations

from datetime import datetime
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
