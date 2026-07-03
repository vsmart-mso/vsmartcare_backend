"""Pydantic schemas สำหรับ address."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ── Nested geo schemas สำหรับ populate ชื่อจังหวัด/อำเภอ/ตำบล/รหัสไปรษณีย์ ──

class _GeoPostcodeRead(BaseModel):
    name: str
    model_config = ConfigDict(from_attributes=True)


class _GeoProvinceRead(BaseModel):
    name: str
    model_config = ConfigDict(from_attributes=True)


class _GeoDistrictRead(BaseModel):
    name: str
    province: _GeoProvinceRead
    model_config = ConfigDict(from_attributes=True)


class _GeoSubDistrictRead(BaseModel):
    name: str
    district: _GeoDistrictRead
    model_config = ConfigDict(from_attributes=True)


class GeoSubDistrictPostcodeRead(BaseModel):
    sub_district: _GeoSubDistrictRead
    postcode: _GeoPostcodeRead
    model_config = ConfigDict(from_attributes=True)


class AddressBase(BaseModel):
    sub_district_postcode_id: int
    applicant_id: int
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
    nearby_landmark: str | None = Field(None, max_length=500)


class AddressCreate(AddressBase):
    pass


class AddressUpdate(BaseModel):
    sub_district_postcode_id: int | None = None
    address_type_id: int | None = None
    alley: str | None = Field(None, max_length=255)
    sub_lane: str | None = Field(None, max_length=255)
    house_name: str | None = Field(None, max_length=255)
    road: str | None = Field(None, max_length=255)
    house_moo: str | None = Field(None, max_length=50)
    house_number: str | None = Field(None, max_length=50)
    mobile_phone: str | None = Field(None, max_length=20)
    latitude: str | None = Field(None, max_length=50)
    longitude: str | None = Field(None, max_length=50)
    nearby_landmark: str | None = Field(None, max_length=500)


class AddressRead(AddressBase):
    id: int
    sub_district_postcode: GeoSubDistrictPostcodeRead | None = None
    model_config = ConfigDict(from_attributes=True)
