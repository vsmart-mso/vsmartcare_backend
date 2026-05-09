"""ข้อมูลเศรษฐกิจ + แหล่งรายได้ของผู้ยื่นคำร้อง.

- economic_infos: ข้อมูลพื้นฐานการเงิน (รายได้/อาชีพ/สมาชิกในครัวเรือน)
- economic_income_sources: junction-with-extras ระหว่าง economic_infos กับ
  income_source_types ตาม ER (composite PK + ฟิลด์ other_details)
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .applicant import Applicant
    from .lookup import HousingType, IncomeSourceType


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

    occupation: Mapped[str | None] = mapped_column(String(255))
    monthly_income: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    household_members: Mapped[int | None] = mapped_column(
        comment="จำนวนสมาชิกในครัวเรือน",
    )
    family_occupation: Mapped[str | None] = mapped_column(String(255))

    applicant: Mapped["Applicant"] = relationship(back_populates="economic_infos")
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
