"""Master/lookup tables (id + name) ตาม ER diagram.

ทุก model ใน file นี้เป็นตารางอ้างอิงเล็ก ๆ (master data) ที่ row น้อย
และไม่ค่อยเปลี่ยน — ใช้สำหรับ FK จาก table หลักอื่น ๆ
"""

from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.base import Base


class LookupMixin:
    """Mixin สำหรับ master table ที่มีโครงสร้าง id + name เหมือนกัน"""

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class PrefixType(LookupMixin, Base):
    """คำนำหน้าชื่อ — นาย, นาง, นางสาว ฯลฯ"""

    __tablename__ = "prefix_type"


class MaritalStatusType(LookupMixin, Base):
    """สถานภาพสมรส — โสด, สมรส, หม้าย ฯลฯ"""

    __tablename__ = "marital_status_types"


class RequestType(LookupMixin, Base):
    """ประเภทคำร้อง"""

    __tablename__ = "request_types"


class AttachmentType(LookupMixin, Base):
    """ประเภทเอกสารแนบ — บัตรประชาชน, ทะเบียนบ้าน ฯลฯ"""

    __tablename__ = "attachment_types"


class ReceivedWelfareType(LookupMixin, Base):
    """ประเภทสวัสดิการที่เคยได้รับ"""

    __tablename__ = "received_welfare_types"


class DependencyType(LookupMixin, Base):
    """ประเภทผู้ที่ต้องเลี้ยงดู (ภาระการเลี้ยงดู)"""

    __tablename__ = "dependency_types"


class HousingType(LookupMixin, Base):
    """ประเภทที่อยู่อาศัย — บ้านตัวเอง, เช่า, อาศัยผู้อื่น ฯลฯ"""

    __tablename__ = "housing_types"


class IncomeSourceType(LookupMixin, Base):
    """ประเภทแหล่งรายได้"""

    __tablename__ = "income_source_types"


class AddressType(LookupMixin, Base):
    """ประเภทที่อยู่ — ตามทะเบียนบ้าน / ปัจจุบัน ฯลฯ"""

    __tablename__ = "address_type"


class CurrentStatus(Base):
    """สถานะคำร้องปัจจุบัน — ตัวนี้ไม่ใช้ LookupMixin เพราะมี description เพิ่ม"""

    __tablename__ = "current_status"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
