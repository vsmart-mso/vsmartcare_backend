"""Master/lookup tables (id + name) ตาม ER diagram.

ทุก model ใน file นี้เป็นตารางอ้างอิงเล็ก ๆ (master data) ที่ row น้อย
และไม่ค่อยเปลี่ยน — ใช้สำหรับ FK จาก table หลักอื่น ๆ
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .applicant import Applicant


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


class RequesterRelationType(LookupMixin, Base):
    """ความสัมพันธ์ผู้ยื่นคำร้องกับผู้รับสิทธิ์ — เช่น ตนเอง"""

    __tablename__ = "requester_relation_type"

    applicants: Mapped[list["Applicant"]] = relationship(
        back_populates="requester_relation_type",
    )


class RequestType(LookupMixin, Base):
    """ประเภทคำร้อง"""

    __tablename__ = "request_types"


class AttachmentType(LookupMixin, Base):
    """ประเภทเอกสารแนบ — รูปหน้าสมุดบัญชี, รูปสมาชิกในครอบครัว (8), รูปอื่น ๆ (99) ฯลฯ"""

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


class BankName(LookupMixin, Base):
    """ชื่อธนาคาร — อ้างอิงจาก applicants.bank_name_id"""

    __tablename__ = "bank_name"

    applicants: Mapped[list["Applicant"]] = relationship(
        back_populates="bank_name",
    )


class AddressType(LookupMixin, Base):
    """ประเภทที่อยู่ — ตามทะเบียนบ้าน / ปัจจุบัน ฯลฯ"""

    __tablename__ = "address_type"


class TypeMoneyCategory(Base):
    """ประเภทเงินช่วยเหลือสำหรับ applicants.type_money_category_id"""

    __tablename__ = "type_money_category"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    name_acronym: Mapped[str] = mapped_column(String(255), nullable=False)
    color: Mapped[str] = mapped_column(String(32), nullable=False)
    name_acrovym_eng: Mapped[str] = mapped_column(String(255), nullable=False)
    activate: Mapped[bool] = mapped_column(default=True, nullable=False)

    applicants: Mapped[list["Applicant"]] = relationship(
        back_populates="type_money_category",
    )


class CurrentStatus(Base):
    """สถานะคำร้องปัจจุบัน — ข้อความแยก public/staff + สีและลำดับ dropdown/filter"""

    __tablename__ = "current_status"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    description_public: Mapped[str] = mapped_column(Text, nullable=False)
    description_staff: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(String(32), nullable=False)
    dropdown_to_change: Mapped[str] = mapped_column(String(255), nullable=False)
    dropdown_order: Mapped[int] = mapped_column(nullable=False)
    dropdown_activate: Mapped[bool] = mapped_column(default=False, nullable=False)
    filter_order: Mapped[int] = mapped_column(nullable=False)
    filter_activate: Mapped[bool] = mapped_column(default=True, nullable=False)
