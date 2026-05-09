"""Pydantic schemas สำหรับ persons — ข้อมูลบุคคลพื้นฐาน."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


def validate_thai_cid(cid: str) -> str:
    """ตรวจ checksum ของเลขบัตรประชาชนไทย 13 หลัก."""
    if len(cid) != 13 or not cid.isdigit():
        raise ValueError("cid ต้องเป็นตัวเลข 13 หลัก")
    digits = [int(c) for c in cid]
    total = sum(d * (13 - i) for i, d in enumerate(digits[:12]))
    check = (11 - total % 11) % 10
    if check != digits[12]:
        raise ValueError("cid checksum ไม่ถูกต้อง")
    return cid


class PersonBase(BaseModel):
    prefix_id: int
    first_name: str = Field(..., min_length=1, max_length=255)
    last_name: str = Field(..., min_length=1, max_length=255)
    cid: str = Field(..., min_length=13, max_length=13)
    birth_date: date
    sub_district_postcode_id: int | None = None
    gender: str | None = Field(None, max_length=50)
    adr_moo: str | None = Field(None, max_length=50)
    adr_house_num: str | None = Field(None, max_length=100)

    @field_validator("cid")
    @classmethod
    def _check_cid(cls, v: str) -> str:
        return validate_thai_cid(v)


class PersonCreate(PersonBase):
    pass


class PersonUpdate(BaseModel):
    prefix_id: int | None = None
    first_name: str | None = Field(None, max_length=255)
    last_name: str | None = Field(None, max_length=255)
    cid: str | None = Field(None, min_length=13, max_length=13)
    birth_date: date | None = None
    sub_district_postcode_id: int | None = None
    gender: str | None = Field(None, max_length=50)
    adr_moo: str | None = Field(None, max_length=50)
    adr_house_num: str | None = Field(None, max_length=100)

    @field_validator("cid")
    @classmethod
    def _check_cid_optional(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return validate_thai_cid(v)


class PersonRead(PersonBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
