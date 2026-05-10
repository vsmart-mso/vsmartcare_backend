"""Pydantic schemas สำหรับ master/lookup tables.

ใช้ pattern Base/Create/Read สำหรับทุก entity:
- Base: ฟิลด์ร่วมระหว่าง create และ read
- Create: input สำหรับสร้าง record (validate)
- Read: output ที่ส่งกลับ client (รวม id + computed fields)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _LookupBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)


class _LookupRead(_LookupBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class PrefixTypeCreate(_LookupBase):
    pass


class PrefixTypeRead(_LookupRead):
    pass


class MaritalStatusTypeCreate(_LookupBase):
    pass


class MaritalStatusTypeRead(_LookupRead):
    pass


class RequestTypeCreate(_LookupBase):
    pass


class RequestTypeRead(_LookupRead):
    pass


class AttachmentTypeCreate(_LookupBase):
    pass


class AttachmentTypeRead(_LookupRead):
    pass


class ReceivedWelfareTypeCreate(_LookupBase):
    pass


class ReceivedWelfareTypeRead(_LookupRead):
    pass


class DependencyTypeCreate(_LookupBase):
    pass


class DependencyTypeRead(_LookupRead):
    pass


class HousingTypeCreate(_LookupBase):
    pass


class HousingTypeRead(_LookupRead):
    pass


class IncomeSourceTypeCreate(_LookupBase):
    pass


class IncomeSourceTypeRead(_LookupRead):
    pass


class AddressTypeCreate(_LookupBase):
    pass


class AddressTypeRead(_LookupRead):
    pass


class CurrentStatusBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class CurrentStatusCreate(CurrentStatusBase):
    pass


class CurrentStatusRead(CurrentStatusBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
