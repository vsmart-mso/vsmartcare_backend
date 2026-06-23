"""ข้อมูลเศรษฐกิจ + แหล่งรายได้ + สมาชิกครัวเรือนของผู้ยื่นคำร้อง.

- economic_infos: ข้อมูลพื้นฐานการเงิน (รายได้/อาชีพ/สมาชิกในครัวเรือน)
- economic_income_sources: junction-with-extras ระหว่าง economic_infos กับ
  income_source_types ตาม ER (composite PK + ฟิลด์ other_details)
- household_members: ข้อมูลสมาชิกในครัวเรือนแบบละเอียด (ปสค.๒)
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .applicant import Applicant
    from .lookup import HouseholdMemberRelationType, HousingType, IncomeSourceType, OccupationType, PrefixType


class EconomicInfo(Base):
    """สถานะทางเศรษฐกิจ (1 record ต่อผู้ยื่น 1 ครั้ง)"""

    __tablename__ = "economic_infos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id"),
        nullable=False,
        index=True,
    )
    housing_types_id: Mapped[int | None] = mapped_column(
        ForeignKey("housing_types.id"),
    )
    housing_types_rent: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        comment="ค่าเช่าต่อเดือน (บาท) — กรอกเมื่อ housing_types เป็นบ้านเช่า",
    )

    occupation_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("occupation_types.id"),
        comment="FK → occupation_types (อาชีพผู้ยื่นคำร้อง)",
    )
    occupation: Mapped[str | None] = mapped_column(String(255))
    monthly_income: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    household_members: Mapped[int | None] = mapped_column(
        comment="จำนวนสมาชิกในครัวเรือน",
    )
    family_occupation_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("occupation_types.id"),
        comment="FK → occupation_types (อาชีพหลักของครอบครัว)",
    )
    family_occupation: Mapped[str | None] = mapped_column(String(255))

    applicant: Mapped["Applicant"] = relationship(back_populates="economic_infos")
    occupation_type: Mapped["OccupationType | None"] = relationship(
        foreign_keys=[occupation_type_id], lazy="selectin"
    )
    family_occupation_type: Mapped["OccupationType | None"] = relationship(
        foreign_keys=[family_occupation_type_id], lazy="selectin"
    )
    housing_type: Mapped["HousingType | None"] = relationship(
        foreign_keys=[housing_types_id],
        lazy="selectin",
    )
    income_sources: Mapped[list["EconomicIncomeSource"]] = relationship(
        back_populates="economic_info",
        cascade="all, delete-orphan",
    )


class EconomicIncomeSource(Base):
    """Junction-with-extras: economic_info x income_source_type พร้อม other_details"""

    __tablename__ = "economic_income_sources"

    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    economic_id: Mapped[int] = mapped_column(
        ForeignKey("economic_infos.id"),
        primary_key=True,
    )
    income_source_type_id: Mapped[int] = mapped_column(
        ForeignKey("income_source_types.id"),
        primary_key=True,
    )

    other_details: Mapped[str | None] = mapped_column(
        String(500),
        comment="กรอกเพิ่มเมื่อเลือกประเภท 'อื่น ๆ'",
    )

    economic_info: Mapped["EconomicInfo"] = relationship(back_populates="income_sources")
    income_source_type: Mapped["IncomeSourceType"] = relationship(lazy="selectin")


class HouseholdMember(Base):
    """ข้อมูลสมาชิกในครัวเรือนแบบละเอียด (ปสค.๒) — หลายแถวต่อ applicant"""

    __tablename__ = "household_members"
    __table_args__ = (
        UniqueConstraint("applicant_id", "seq", name="uq_household_members_applicant_seq"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seq: Mapped[int] = mapped_column(nullable=False, comment="ลำดับสมาชิกในครัวเรือน")
    national_id: Mapped[str | None] = mapped_column(String(13), comment="เลขบัตรประชาชน (ถ้ามี)")
    prefix_id: Mapped[int | None] = mapped_column(ForeignKey("prefix_type.id"))
    prefix_other: Mapped[str | None] = mapped_column(String(50), comment="คำนำหน้าอื่นๆ")
    first_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="ชื่อ")
    last_name: Mapped[str] = mapped_column(String(255), nullable=False, comment="สกุล")
    date_of_birth: Mapped[date | None] = mapped_column(nullable=True, comment="วันเกิด — อายุคำนวณจาก field นี้")
    relation_to_applicant_id: Mapped[int | None] = mapped_column(
        ForeignKey("household_member_relation_types.id"),
        comment="FK → household_member_relation_types",
    )
    occupation_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("occupation_types.id"),
        comment="FK → occupation_types",
    )
    occupation: Mapped[str | None] = mapped_column(String(255), comment="อาชีพ (free-text เมื่อ occupation_type_id=99)")
    monthly_income: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), comment="รายได้/เดือน (บาท)")
    physical_condition: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="normal",
        comment="สภาพทางร่างกาย: normal/disabled/chronic_illness",
    )
    self_care: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="true",
        comment="ช่วยเหลือตนเองได้: true=ได้ / false=ไม่ได้",
    )

    applicant: Mapped["Applicant"] = relationship(back_populates="household_members")
    prefix: Mapped["PrefixType | None"] = relationship(
        foreign_keys=[prefix_id], lazy="selectin"
    )
    relation_type: Mapped["HouseholdMemberRelationType | None"] = relationship(
        foreign_keys=[relation_to_applicant_id], lazy="selectin"
    )
    occupation_type: Mapped["OccupationType | None"] = relationship(
        foreign_keys=[occupation_type_id], lazy="selectin"
    )
