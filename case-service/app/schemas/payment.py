"""Pydantic schemas สำหรับ approve_case / welfare_payment / welfare_dda_ref / file_payment."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ApproveCaseBase(BaseModel):
    applicant_id: int
    approve_status: bool = False
    esignature: str | None = None
    user_sdshv: str | None = Field(None, max_length=255)
    reject_reason: str | None = Field(
        None,
        min_length=1,
        description="เหตุผลที่ พมจ. ไม่อนุมัติ บังคับเมื่อ approve_status=false",
    )


class ApproveCaseCreate(ApproveCaseBase):
    @model_validator(mode="after")
    def validate_reject_reason(self) -> "ApproveCaseCreate":
        if self.approve_status:
            if self.reject_reason and self.reject_reason.strip():
                raise ValueError("reject_reason_must_be_empty_when_approved")
            self.reject_reason = None
            return self

        reason = (self.reject_reason or "").strip()
        if not reason:
            raise ValueError("reject_reason_required")
        self.reject_reason = reason
        return self


class ApproveCaseRead(ApproveCaseBase):
    id: int
    article_id: int | None = None
    reject_resolved_at: datetime | None = None
    model_config = ConfigDict(from_attributes=True)


class WelfareDdaRefBase(BaseModel):
    dda_ref: str = Field(..., min_length=1, max_length=255)
    user_sdshv: str | None = Field(None, max_length=255)


class WelfareDdaRefCreate(WelfareDdaRefBase):
    pass


class WelfareDdaRefRead(WelfareDdaRefBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class WelfareDdaRefDetailCreate(BaseModel):
    """หนึ่ง applicant ที่ผูกกับหมายเลข dda_ref ผ่าน welfare_payment."""

    applicant_id: int = Field(..., ge=1)


class WelfareDdaRefBundleCreate(BaseModel):
    """สร้าง welfare_dda_ref พร้อม welfare_payment หลายรายการ (ฟิลด์จ่ายเงินว่าง — อัปเดตภายหลัง)."""

    dda_ref: str = Field(..., min_length=1, max_length=255, description="หมายเลขอ้างอิง DDA")
    dda_ref_detail: list[WelfareDdaRefDetailCreate] = Field(
        ...,
        min_length=1,
        description="รายการ applicant_id ที่ผูกกับ dda_ref นี้",
    )
    user_sdshv: str | None = Field(
        None,
        max_length=255,
        description="ผู้บันทึกฝั่ง welfare_dda_ref (ไม่ใช่ฟิลด์บน welfare_payment)",
    )


class WelfarePaymentInitialRead(BaseModel):
    """แถว welfare_payment หลังสร้าง — ฟิลด์จ่ายเงินยังว่าง."""

    id: int
    applicant_id: int
    dda_ref_id: int
    is_037_or_038: bool | None = None
    payment_number: str | None = None
    payment_038_reason: str | None = None
    user_sdshv: str | None = None
    transaction_date: date | None = None
    effective_date: date | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class WelfareDdaRefBundleRead(BaseModel):
    id: int
    dda_ref: str
    user_sdshv: str | None = None
    welfare_payments: list[WelfarePaymentInitialRead] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class WelfarePaymentBase(BaseModel):
    applicant_id: int
    is_037_or_038: bool | None = None
    dda_ref_id: int
    payment_number: str | None = Field(None, max_length=255)
    payment_038_reason: str | None = Field(None, max_length=255)
    user_sdshv: str | None = Field(None, max_length=255)
    transaction_date: date | None = None
    effective_date: date | None = None


class WelfarePaymentCreate(WelfarePaymentBase):
    pass


class WelfarePaymentRead(WelfarePaymentBase):
    id: int
    created_at: datetime | None = None
    upload_batch_id: UUID | None = None
    model_config = ConfigDict(from_attributes=True)


class WelfarePaymentUpdate(BaseModel):
    """อัปเดต welfare_payment (ส่งเฉพาะฟิลด์ที่ต้องการเปลี่ยน)."""

    is_037_or_038: bool | None = Field(
        None,
        description="false = 037, true = 038",
    )
    payment_number: str | None = Field(None, max_length=255)
    payment_038_reason: str | None = Field(None, max_length=255)
    transaction_date: date | None = None
    effective_date: date | None = None
    user_sdshv: str | None = Field(None, max_length=255)
    upload_batch_id: UUID | None = Field(
        None,
        description="UUID ร่วมกันต่อการบันทึกครั้งเดียวใน modal (037+038)",
    )


class WelfarePaymentPartial(BaseModel):
    """ฟิลด์ฝั่ง 037 หรือ 038 สำหรับบันทึกคู่ในครั้งเดียว (ไม่ส่ง is_037_or_038)."""

    payment_number: str | None = Field(None, max_length=255)
    payment_038_reason: str | None = Field(None, max_length=255)
    transaction_date: date | None = None
    effective_date: date | None = None


class WelfarePaymentBatchUpdate(BaseModel):
    """บันทึก 037 และ 038 ใน transaction เดียว — ใช้ upload_batch_id ร่วมกัน."""

    upload_batch_id: UUID = Field(..., description="UUID ร่วมกันต่อการบันทึกครั้งเดียวใน modal")
    user_sdshv: str | None = Field(None, max_length=255)
    payment_037: WelfarePaymentPartial
    payment_038: WelfarePaymentPartial


class WelfarePaymentBatchRead(BaseModel):
    payment_037: WelfarePaymentRead
    payment_038: WelfarePaymentRead


class FilePaymentBase(BaseModel):
    welfare_dda_ref_id: int
    welfare_payment_id: int | None = Field(
        None,
        ge=1,
        description="แถว welfare_payment ที่ไฟล์นี้ผูก (แนะนำส่งหลัง PATCH 038)",
    )
    file_original_name: str | None = Field(None, max_length=255)
    file_stored_name: str | None = Field(None, max_length=255)
    file_path: str = Field(..., max_length=1024)
    file_size: int | None = Field(None, ge=0)
    file_width: int | None = Field(None, ge=0)
    file_height: int | None = Field(None, ge=0)
    attachment_type_id: int


class FilePaymentCreate(FilePaymentBase):
    pass


class FilePaymentRead(FilePaymentBase):
    id: int
    upload_batch_id: UUID | None = None
    model_config = ConfigDict(from_attributes=True)


class FilePaymentUploadRead(FilePaymentRead):
    """ผลหลังอัปโหลด PDF — มี path สำหรับดาวน์โหลด."""

    view_path: str = Field(
        ...,
        description="GET path สำหรับดาวน์โหลดไฟล์ — ต่อกับ base URL ของ case-service หรือ BFF",
    )


class PaymentUploadFileItem(BaseModel):
    """ไฟล์หนึ่งรายการในรอบอัปโหลด — ใช้ view_path ดาวน์โหลด."""

    label: str = Field(..., description="cft037 หรือ cft038")
    file_payment_id: int
    file_original_name: str | None = None
    view_path: str = Field(
        ...,
        description="GET path ดาวน์โหลด — ต่อกับ base URL ของ case-service หรือ BFF",
    )


class PaymentUploadHistoryRound(BaseModel):
    """หนึ่งรอบ (ครั้งที่) ของการบันทึก/อัปโหลด 037–038."""

    round_no: int = Field(..., ge=1, description="ครั้งที่ (เรียงตาม id ของ welfare_payment)")
    welfare_payment_id: int = Field(
        ...,
        ge=1,
        description="แถว anchor ของรอบ (038 ก่อน หรือแถวเดียว) — ใช้ welfare_payment_id_037/_038 เมื่อแก้ไข",
    )
    welfare_payment_id_037: int | None = Field(
        None,
        ge=1,
        description="แถว welfare_payment ของ 037 ในรอบนี้ (ถ้ามี)",
    )
    welfare_payment_id_038: int | None = Field(
        None,
        ge=1,
        description="แถว welfare_payment ของ 038 ในรอบนี้ (ถ้ามี)",
    )
    payment_id_cft037: str | None = Field(
        None,
        description="Payment ID / เลขอ้างอิง CFT 037 (payment_number จากแถว 037)",
    )
    payment_id_cft038: str | None = Field(
        None,
        description="Payment ID / เลขอ้างอิง CFT 038 (payment_number จากแถว 038)",
    )
    files: list[str] = Field(
        default_factory=list,
        description='ป้ายไฟล์ที่อัปโหลดในรอบนี้ เช่น ["cft037", "cft038"]',
    )
    file_items: list[PaymentUploadFileItem] = Field(
        default_factory=list,
        description="รายละเอียดไฟล์พร้อมลิงก์ดาวน์โหลด",
    )
    reason: str | None = Field(None, description="เหตุผล (payment_038_reason)")
    uploaded_at: datetime | None = Field(
        None,
        description="วันเวลาบันทึกรอบ — จาก welfare_payment.created_at",
    )
    transaction_date: date | None = Field(
        None,
        description="วันที่ทำรายการ — จาก welfare_payment.transaction_date",
    )
    effective_date: date | None = Field(
        None,
        description="วันที่มีผล — จาก welfare_payment.effective_date",
    )
    upload_batch_id: UUID | None = Field(
        None,
        description="รหัสชุดอัปโหลดเดียวกัน (modal เดียว)",
    )


class PaymentUploadHistoryRead(BaseModel):
    """ประวัติการอัปโหลด PDF 037/038 ของ applicant."""

    applicant_id: int
    case_number: str | None = Field(None, description="หมายเลขคำร้อง")
    rounds: list[PaymentUploadHistoryRound] = Field(default_factory=list)
