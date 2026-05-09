"""Pydantic schemas สำหรับ address."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AddressBase(BaseModel):
    sub_district_postcode_id: int
    applicant_id: int
    address_type_id: int

    sub_lane: str | None = Field(None, max_length=255)
    house_name: str | None = Field(None, max_length=255)
    road: str | None = Field(None, max_length=255)
    house_moo: str | None = Field(None, max_length=50)
    house_number: str | None = Field(None, max_length=50)
    mobile_phone: str | None = Field(None, max_length=20)

    latitude: str | None = Field(None, max_length=50)
    longitude: str | None = Field(None, max_length=50)


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    sub_district_postcode_id: int | None = None
    address_type_id: int | None = None
    sub_lane: str | None = Field(None, max_length=255)
    house_name: str | None = Field(None, max_length=255)
    road: str | None = Field(None, max_length=255)
    house_moo: str | None = Field(None, max_length=50)
    house_number: str | None = Field(None, max_length=50)
    mobile_phone: str | None = Field(None, max_length=20)
    latitude: str | None = Field(None, max_length=50)
    longitude: str | None = Field(None, max_length=50)


class AddressRead(AddressBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
