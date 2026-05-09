"""ตารางหลัก `applicants` — ข้อมูลผู้ขอรับสวัสดิการ.

ผูกกับ `persons` ผ่าน persons_id (ข้อมูลชื่อ/เลขบัตรอยู่ที่ persons)
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .address import Address
    from .dependency import DependencyLoad
    from .economic import EconomicInfo
    from .lookup import MaritalStatusType
    from .person import Person
    from .status_log import WelfareRequestStatus
    from .welfare import (
        WelfareEvidence,
        WelfareHistory,
        WelfareRequestType,
    )


class Applicant(Base):
    """ข้อมูลผู้ขอรับสวัสดิการ"""

    __tablename__ = "applicants"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    persons_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id"),
        nullable=False,
        index=True,
    )

    requester_relation: Mapped[str | None] = mapped_column(String(100))
    marital_status_id: Mapped[int] = mapped_column(
        ForeignKey("marital_status_types.id"),
        nullable=False,
    )

    mobile_phone: Mapped[str | None] = mapped_column(String(20))
    home_phone: Mapped[str | None] = mapped_column(String(20))
    fax_number: Mapped[str | None] = mapped_column(String(20))
    email_address: Mapped[str | None] = mapped_column(String(255))

    is_government_officer: Mapped[bool] = mapped_column(default=False, nullable=False)

    problem_details: Mapped[str | None] = mapped_column(Text)

    bank_account_name: Mapped[str | None] = mapped_column(String(255))
    bank_account_no: Mapped[str | None] = mapped_column(String(50))

    time_count_process: Mapped[int | None] = mapped_column()

    is_emergency: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_existing_case: Mapped[bool] = mapped_column(default=False, nullable=False)

    person: Mapped["Person"] = relationship(back_populates="applicants", lazy="selectin")
    marital_status: Mapped["MaritalStatusType"] = relationship(lazy="selectin")

    addresses: Mapped[list["Address"]] = relationship(
        back_populates="applicant",
        cascade="all, delete-orphan",
    )
    economic_infos: Mapped[list["EconomicInfo"]] = relationship(
        back_populates="applicant",
        cascade="all, delete-orphan",
    )
    dependency_loads: Mapped[list["DependencyLoad"]] = relationship(
        back_populates="applicant",
        cascade="all, delete-orphan",
    )
    welfare_history: Mapped["WelfareHistory | None"] = relationship(
        back_populates="applicant",
        uselist=False,
        cascade="all, delete-orphan",
    )
    welfare_request_types: Mapped[list["WelfareRequestType"]] = relationship(
        back_populates="applicant",
        cascade="all, delete-orphan",
    )
    welfare_evidences: Mapped[list["WelfareEvidence"]] = relationship(
        back_populates="applicant",
        cascade="all, delete-orphan",
    )
    status_logs: Mapped[list["WelfareRequestStatus"]] = relationship(
        back_populates="applicant",
        cascade="all, delete-orphan",
        order_by="WelfareRequestStatus.updated_at.desc()",
    )
