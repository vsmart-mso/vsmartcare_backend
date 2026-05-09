"""Pydantic schemas สำหรับโครงสร้างที่อยู่ (geo hierarchy)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProvinceBase(BaseModel):
    code: str | None = Field(None, max_length=10)
    name: str = Field(..., min_length=1, max_length=255)


class ProvinceCreate(ProvinceBase):
    pass


class ProvinceRead(ProvinceBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class DistrictBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    province_id: int


class DistrictCreate(DistrictBase):
    pass


class DistrictRead(DistrictBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class SubDistrictBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    district_id: int


class SubDistrictCreate(SubDistrictBase):
    pass


class SubDistrictRead(SubDistrictBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class PostcodeBase(BaseModel):
    name: str = Field(..., min_length=5, max_length=10)


class PostcodeCreate(PostcodeBase):
    pass


class PostcodeRead(PostcodeBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class SubDistrictPostcodeBase(BaseModel):
    sub_district_id: int
    postcode_id: int


class SubDistrictPostcodeCreate(SubDistrictPostcodeBase):
    pass


class SubDistrictPostcodeRead(SubDistrictPostcodeBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
