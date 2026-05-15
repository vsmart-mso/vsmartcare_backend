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


class WelfarePaymentBase(BaseModel):
    applicant_id: int
    is_037_or_038: bool = False
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
