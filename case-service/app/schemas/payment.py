"""Pydantic schemas สำหรับ approve_case / welfare_payment / welfare_dda_ref / file_payment."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ApproveCaseBase(BaseModel):
    applicant_id: int
    approve_status: bool = False
    esignature: str | None = None
    user_sdshv: str | None = Field(None, max_length=255)


class ApproveCaseCreate(ApproveCaseBase):
    pass


class ApproveCaseRead(ApproveCaseBase):
    id: int
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
    model_config = ConfigDict(from_attributes=True)


class WelfarePaymentUpdate(BaseModel):
    """อัปเดต welfare_payment (ส่งเฉพาะฟิลด์ที่ต้องการเปลี่ยน)."""

    is_037_or_038: bool | None = None
    payment_number: str | None = Field(None, max_length=255)
    payment_038_reason: str | None = Field(None, max_length=255)
    transaction_date: date | None = None
    effective_date: date | None = None
    user_sdshv: str | None = Field(None, max_length=255)


class FilePaymentBase(BaseModel):
    welfare_dda_ref_id: int
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
    model_config = ConfigDict(from_attributes=True)


class FilePaymentUploadRead(FilePaymentRead):
    """ผลหลังอัปโหลด PDF — มี path สำหรับดาวน์โหลด."""

    view_path: str = Field(
        ...,
        description="GET path สำหรับดาวน์โหลดไฟล์ — ต่อกับ base URL ของ case-service หรือ BFF",
    )
