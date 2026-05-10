"""ตาราง `persons` — ข้อมูลบุคคลพื้นฐาน (แยกจาก applicants).

ใช้ร่วมกับ applicants (FK persons_id), screening_logs, welfare_request_consents
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .applicant import Applicant
    from .geo import SubDistrictPostcode
    from .lookup import PrefixType
    from .screening import ScreeningLog, WelfareRequestConsent


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    prefix_id: Mapped[int] = mapped_column(
        ForeignKey("prefix_type.id"),
        nullable=False,
    )
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cid: Mapped[str] = mapped_column(
        String(13),
        nullable=False,
        unique=True,
        index=True,
        comment="เลขบัตรประจำตัวประชาชน 13 หลัก",
    )
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)

    sub_district_postcode_id: Mapped[int | None] = mapped_column(
        ForeignKey("sub_districts_postcode.id"),
        nullable=True,
        index=True,
    )
    gender: Mapped[str | None] = mapped_column(String(50))
    adr_moo: Mapped[str | None] = mapped_column(String(50))
    adr_house_num: Mapped[str | None] = mapped_column(String(100))

    prefix: Mapped["PrefixType"] = relationship(lazy="selectin")
    sub_district_postcode: Mapped["SubDistrictPostcode | None"] = relationship(
        lazy="selectin"
    )
    applicants: Mapped[list["Applicant"]] = relationship(
        back_populates="person",
        cascade="all, delete-orphan",
    )
    screening_logs: Mapped[list["ScreeningLog"]] = relationship(
        "ScreeningLog",
        back_populates="person",
        cascade="all, delete-orphan",
    )
    consents: Mapped[list["WelfareRequestConsent"]] = relationship(
        "WelfareRequestConsent",
        back_populates="person",
        cascade="all, delete-orphan",
    )
