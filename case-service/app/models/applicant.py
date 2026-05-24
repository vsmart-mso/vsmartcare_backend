"""ตารางหลัก `applicants` — ข้อมูลผู้ขอรับสวัสดิการ.

ผูกกับ `persons` ผ่าน persons_id (ข้อมูลชื่อ/เลขบัตรอยู่ที่ persons)
และ `requester_relation_type` ผ่าน requester_relation_id
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .address import Address
    from .dependency import DependencyLoad
    from .economic import EconomicInfo
    from .intake import CaseHandling
    from .lookup import BankName, MaritalStatusType, RequesterRelationType, TypeMoneyCategory
    from .payment import ApproveCase, WelfarePayment
    from .person import Person
    from .satisfaction import SatisfactionSurvey
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

    case_number: Mapped[str | None] = mapped_column(String(100))

    requester_relation_id: Mapped[int] = mapped_column(
        ForeignKey("requester_relation_type.id"),
        nullable=False,
        index=True,
    )
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

    bank_name_id: Mapped[int | None] = mapped_column(
        ForeignKey("bank_name.id"),
        index=True,
    )
    bank_account_no: Mapped[str | None] = mapped_column(String(50))
    # ประเภทเงินฝาก — FK ไปยัง master bank_account_type (เก็บค่าที่ OCR อ่าน+map แล้ว)
    bank_account_type_id: Mapped[int | None] = mapped_column(
        ForeignKey("bank_account_type.id"),
        index=True,
    )
    # ชื่อสาขา — ข้อความจาก OCR (ไม่ผูก lookup)
    bank_branch_name: Mapped[str | None] = mapped_column(String(255))
    type_money_category_id: Mapped[int | None] = mapped_column(
        ForeignKey("type_money_category.id"),
        index=True,
    )
    sw_explorer_sdshv: Mapped[str | None] = mapped_column(String(255))

    time_count_process: Mapped[int | None] = mapped_column()

    process_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    process_sla_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_emergency: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_existing_case: Mapped[bool] = mapped_column(default=False, nullable=False)

    age: Mapped[int | None] = mapped_column()

    person: Mapped["Person"] = relationship(back_populates="applicants", lazy="selectin")
    requester_relation_type: Mapped["RequesterRelationType"] = relationship(
        back_populates="applicants",
        lazy="selectin",
    )
    marital_status: Mapped["MaritalStatusType"] = relationship(lazy="selectin")
    bank_name: Mapped["BankName | None"] = relationship(
        back_populates="applicants",
        lazy="selectin",
    )
    type_money_category: Mapped["TypeMoneyCategory | None"] = relationship(
        back_populates="applicants",
        lazy="selectin",
    )

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
    approve_cases: Mapped[list["ApproveCase"]] = relationship(
        back_populates="applicant",
        cascade="all, delete-orphan",
    )
    welfare_payments: Mapped[list["WelfarePayment"]] = relationship(
        back_populates="applicant",
        cascade="all, delete-orphan",
    )
    case_handling: Mapped["CaseHandling | None"] = relationship(
        back_populates="applicant",
        uselist=False,
        cascade="all, delete-orphan",
    )
    satisfaction_surveys: Mapped[list["SatisfactionSurvey"]] = relationship(
        cascade="all, delete-orphan",
    )
