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


class RequesterRelationTypeCreate(_LookupBase):
    pass


class RequesterRelationTypeRead(_LookupRead):
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


class BankNameBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    bank_id_mso: int = Field(..., ge=0)
    bank_code: str = Field(..., min_length=1, max_length=10)
    order: int = Field(..., ge=0)


class BankNameCreate(BankNameBase):
    pass


class BankNameRead(BankNameBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class AddressTypeCreate(_LookupBase):
    pass


class AddressTypeRead(_LookupRead):
    pass


class TypeMoneyCreate(_LookupBase):
    pass


class TypeMoneyRead(_LookupRead):
    pass


class BankAccountTypeRead(BaseModel):
    id: int
    name: str
    sort_order: int | None = None

    model_config = ConfigDict(from_attributes=True)


class TypeMoneyCategoryBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    name_acronym: str = Field(..., min_length=1, max_length=255)
    color: str = Field(..., min_length=1, max_length=32)
    name_acrovym_eng: str = Field(..., min_length=1, max_length=255)
    activate: bool = True


class TypeMoneyCategoryCreate(TypeMoneyCategoryBase):
    pass


class TypeMoneyCategoryRead(TypeMoneyCategoryBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class CurrentStatusBase(BaseModel):
    description_public: str = Field(..., min_length=1)
    description_staff: str = Field(..., min_length=1)
    color: str = Field(..., min_length=1, max_length=32)
    dropdown_to_change: str = Field(..., min_length=1, max_length=255)
    dropdown_order: int = Field(..., ge=0)
    dropdown_activate: bool = False
    filter_order: int = Field(..., ge=0)
    filter_activate: bool = True
    vsmart_id: int = Field(..., ge=1)


class CurrentStatusCreate(CurrentStatusBase):
    pass


class CurrentStatusRead(CurrentStatusBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
