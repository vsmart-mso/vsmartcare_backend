"""Pydantic schemas สำหรับ address."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AddressBase(BaseModel):
    sub_district_postcode_id: int
    applicant_id: int
    address_type_id: int

    address_detail: str | None = Field(None, max_length=500)
    sub_lane_road: str | None = Field(None, max_length=255)
    mobile_phone: str | None = Field(None, max_length=20)

    latitude: str | None = Field(None, max_length=50)
    longitude: str | None = Field(None, max_length=50)


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    sub_district_postcode_id: int | None = None
    address_type_id: int | None = None
    address_detail: str | None = Field(None, max_length=500)
    sub_lane_road: str | None = Field(None, max_length=255)
    mobile_phone: str | None = Field(None, max_length=20)
    latitude: str | None = Field(None, max_length=50)
    longitude: str | None = Field(None, max_length=50)


class AddressRead(AddressBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
