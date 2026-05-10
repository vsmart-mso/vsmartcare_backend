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
    code: str | None = Field(None, max_length=50)
    model_config = ConfigDict(from_attributes=True)


class SubDistrictBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    district_id: int


class SubDistrictCreate(SubDistrictBase):
    pass


class SubDistrictRead(SubDistrictBase):
    id: int
    code: str | None = Field(None, max_length=50)
    model_config = ConfigDict(from_attributes=True)


class PostcodeBase(BaseModel):
    name: str = Field(..., min_length=5, max_length=10)


class PostcodeCreate(PostcodeBase):
    pass


class PostcodeRead(PostcodeBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class SubDistrictPostcodeLinkRead(BaseModel):
    """แถวตาราง sub_districts_postcode + postcode — ใช้ `id` ตอนบันทึกที่อยู่ (FK bridge)"""

    id: int
    sub_district_id: int
    postcode_id: int
    postcode: PostcodeRead
    model_config = ConfigDict(from_attributes=True)


class SubDistrictWithPostcodesRead(BaseModel):
    """ตำบลพร้อมรหัสไปรษณีย์ (ผ่าน sub_districts_postcode — 1 ตำบลได้หลายรหัส)"""

    id: int
    code: str | None = Field(None, max_length=50)
    name: str
    district_id: int
    postcodes: list[PostcodeRead] = Field(default_factory=list)
    sub_districts_postcode: list[SubDistrictPostcodeLinkRead] = Field(
        default_factory=list,
        description="แถว bridge sub_districts_postcode ทั้งหมดของตำบลนี้ (ส่งกลับเพื่อใช้ตอนบันทึก)",
    )
    model_config = ConfigDict(from_attributes=True)


class SubDistrictPostcodeBase(BaseModel):
    sub_district_id: int
    postcode_id: int


class SubDistrictPostcodeCreate(SubDistrictPostcodeBase):
    pass


class SubDistrictPostcodeRead(SubDistrictPostcodeBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
