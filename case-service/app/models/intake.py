"""ORM models สำหรับ payment intake flow — หน้า 11, 13, 20 (v2).

ตารางใหม่ที่สร้างใน migration 0020–0026:
  - AnnouncementRegulation  (master ระเบียบ/ประกาศ)
  - CaseHandling            (hub รับเรื่อง 1:1 applicants)
  - CaseRegulationChoice    (ระเบียบที่เลือก หน้า 11)
  - PaymentMethod           (master วิธีจ่ายเงิน 6 แถว)
  - CasePayment             (วิธีจ่ายเงินตอนรับเรื่อง หน้า 13)
  - CaseKtbCorporate        (ข้อมูล KTB Corporate หน้า 20)
  - type_money (lookup)     FK บน case_handling.type_money_id
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .applicant import Applicant
    from .lookup import BankName, TypeMoney, TypeMoneyCategory
    from .person import Person


# ---------------------------------------------------------------------------
# Enums (สร้าง type ใน DB แล้วใน migration 0022 — create_type=False)
# ---------------------------------------------------------------------------


class KtbRecipientCategory(str, enum.Enum):
    payroll = "payroll"
    gov_other = "gov_other"
    external = "external"


class KtbNotifyChannel(str, enum.Enum):
    sms = "sms"
    email = "email"


# ---------------------------------------------------------------------------
# AnnouncementRegulation — master ระเบียบ/ประกาศ (seed id ตรงกับ VSmart)
# ---------------------------------------------------------------------------


class AnnouncementRegulation(Base):
    """master ระเบียบ/ประกาศ — dropdown หน้า 11 (id sync ตรงกับ VSmart)"""

    __tablename__ = "announcement_regulations"

    # id ไม่ใช้ autoincrement — กำหนดตรงจาก VSmart เพื่อ sync
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100))
    type_money_category_id: Mapped[int] = mapped_column(
        ForeignKey("type_money_category.id"),
        nullable=False,
        index=True,
    )
    maximum_money: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    limit_per_budget_year: Mapped[int] = mapped_column(nullable=False)
    sort_order: Mapped[int | None] = mapped_column()
    activate: Mapped[bool] = mapped_column(default=True, nullable=False)
    vsmart_legacy_id: Mapped[int | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    type_money_category: Mapped["TypeMoneyCategory"] = relationship(
        back_populates="announcement_regulations",
        lazy="selectin",
    )
    regulation_choices: Mapped[list["CaseRegulationChoice"]] = relationship(
        back_populates="regulation",
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# CaseHandling — hub รับเรื่อง 1:1 กับ applicants
# ---------------------------------------------------------------------------


class CaseHandling(Base):
    """hub รับเรื่อง — สร้างหลังหน้า 11, 1:1 กับ applicants"""

    __tablename__ = "case_handling"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    vsmart_informer_id: Mapped[int | None] = mapped_column()
    vsmart_social_worker_id: Mapped[int | None] = mapped_column()
    sw_user_sdshv: Mapped[str | None] = mapped_column(String(255))
    type_money_id: Mapped[int | None] = mapped_column(
        ForeignKey("type_money.id"),
        nullable=True,
        index=True,
    )
    intake_completed_at: Mapped[datetime | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    applicant: Mapped["Applicant"] = relationship(
        back_populates="case_handling",
        lazy="selectin",
    )
    type_money: Mapped["TypeMoney | None"] = relationship(
        back_populates="case_handlings",
        lazy="selectin",
    )
    regulation_choice: Mapped["CaseRegulationChoice | None"] = relationship(
        back_populates="case_handling",
        uselist=False,
        cascade="all, delete-orphan",
    )
    payment: Mapped["CasePayment | None"] = relationship(
        back_populates="case_handling",
        uselist=False,
        cascade="all, delete-orphan",
    )
    ktb_corporate: Mapped["CaseKtbCorporate | None"] = relationship(
        back_populates="case_handling",
        uselist=False,
        cascade="all, delete-orphan",
    )


# ---------------------------------------------------------------------------
# CaseRegulationChoice — ระเบียบที่เลือก + วงเงิน + ลายเซ็น (หน้า 11)
# ---------------------------------------------------------------------------


class CaseRegulationChoice(Base):
    """ระเบียบที่เลือก + วงเงิน + ลายเซ็น — 1:1 case_handling"""

    __tablename__ = "case_regulation_choice"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_handling_id: Mapped[int] = mapped_column(
        ForeignKey("case_handling.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    regulation_id: Mapped[int] = mapped_column(
        ForeignKey("announcement_regulations.id"),
        nullable=False,
        index=True,
    )
    help_kind: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        server_default="money",
        comment="money | things",
    )
    money_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    comment: Mapped[str | None] = mapped_column(Text)
    esignature: Mapped[str | None] = mapped_column(Text)
    signed_by_sdshv: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    case_handling: Mapped["CaseHandling"] = relationship(back_populates="regulation_choice")
    regulation: Mapped["AnnouncementRegulation"] = relationship(
        back_populates="regulation_choices",
        lazy="selectin",
    )


# ---------------------------------------------------------------------------
# PaymentMethod — master วิธีจ่ายเงิน 6 แถว (seed 0021)
# ---------------------------------------------------------------------------


class PaymentMethod(Base):
    """master วิธีจ่ายเงิน — seed 6 แถว: cash, cheque, bank_transfer, promptpay, ktb_corporate, epayment"""

    __tablename__ = "payment_method"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    name_th: Mapped[str] = mapped_column(String(255), nullable=False)
    legacy_vsmart_value: Mapped[str | None] = mapped_column(
        String(10),
        comment="transfer_money_type จาก VSmart: False/True/0/1/2/3",
    )
    sort_order: Mapped[int] = mapped_column(nullable=False)
    requires_ktb_form: Mapped[bool] = mapped_column(default=False, nullable=False)

    case_payments: Mapped[list["CasePayment"]] = relationship(
        back_populates="payment_method",
    )


# ---------------------------------------------------------------------------
# CasePayment — วิธีจ่ายเงินตอนรับเรื่อง หน้า 13 (ไม่ใช่ welfare_payment)
# ---------------------------------------------------------------------------


class CasePayment(Base):
    """วิธีจ่ายเงินที่เลือกตอนรับเรื่อง — 1:1 case_handling

    ไม่ใช่ welfare_payment ซึ่งบันทึกหลัง DDA/จ่ายจริง
    """

    __tablename__ = "case_payment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_handling_id: Mapped[int] = mapped_column(
        ForeignKey("case_handling.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    payment_method_id: Mapped[int] = mapped_column(
        ForeignKey("payment_method.id"),
        nullable=False,
        index=True,
    )
    receive_mode: Mapped[str | None] = mapped_column(
        String(10),
        comment="self | agent — NULL ได้ถ้ายังไม่ระบุ",
    )
    agent_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id"),
        index=True,
    )
    payee_person_id: Mapped[int | None] = mapped_column(
        ForeignKey("persons.id"),
        index=True,
    )
    bank_name_id: Mapped[int | None] = mapped_column(
        ForeignKey("bank_name.id"),
        index=True,
    )
    bank_branch: Mapped[str | None] = mapped_column(String(255))
    account_type: Mapped[str | None] = mapped_column(String(100))
    account_number: Mapped[str | None] = mapped_column(String(50))
    account_name: Mapped[str | None] = mapped_column(String(255))
    cheque_reference: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    case_handling: Mapped["CaseHandling"] = relationship(back_populates="payment")
    payment_method: Mapped["PaymentMethod"] = relationship(
        back_populates="case_payments",
        lazy="selectin",
    )
    bank_name: Mapped["BankName | None"] = relationship(
        foreign_keys=[bank_name_id],
        lazy="selectin",
    )
    agent_person: Mapped["Person | None"] = relationship(
        foreign_keys=[agent_person_id],
        lazy="selectin",
    )
    payee_person: Mapped["Person | None"] = relationship(
        foreign_keys=[payee_person_id],
        lazy="selectin",
    )


# ---------------------------------------------------------------------------
# CaseKtbCorporate — KTB Corporate Online หน้า 20 (เฉพาะ ktb_corporate)
# ---------------------------------------------------------------------------


class CaseKtbCorporate(Base):
    """ข้อมูล KTB Corporate Online — 1:1 case_handling, สร้างหลังหน้า 20

    recipient_category:
      payroll   → ข้อ 1.1 ข้าราชการรับเงินเดือน (ใช้ payroll_*)
      gov_other → ข้อ 1.2 ข้าราชการอื่นที่ผ่านบัญชีอนุญาต (ใช้ other_*)
      external  → ข้อ 2 บุคคลภายนอก (อ้างข้อมูลบัญชีจาก case_payment ไม่ duplicate)
    """

    __tablename__ = "case_ktb_corporate"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_handling_id: Mapped[int] = mapped_column(
        ForeignKey("case_handling.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    form_number: Mapped[int | None] = mapped_column()
    director_division_ref: Mapped[str | None] = mapped_column(String(500))
    paying_division_ref: Mapped[str | None] = mapped_column(String(500))
    recipient_category: Mapped[KtbRecipientCategory] = mapped_column(
        SAEnum(KtbRecipientCategory, name="ktb_recipient_category", create_type=False),
        nullable=False,
    )
    payroll_bank_name_id: Mapped[int | None] = mapped_column(
        ForeignKey("bank_name.id"),
        index=True,
    )
    payroll_bank_branch: Mapped[str | None] = mapped_column(String(255))
    payroll_account_type: Mapped[str | None] = mapped_column(String(100))
    payroll_account_number: Mapped[str | None] = mapped_column(String(50))
    other_bank_name_id: Mapped[int | None] = mapped_column(
        ForeignKey("bank_name.id"),
        index=True,
    )
    other_bank_branch: Mapped[str | None] = mapped_column(String(255))
    other_account_type: Mapped[str | None] = mapped_column(String(100))
    other_account_number: Mapped[str | None] = mapped_column(String(50))
    notify_channel: Mapped[KtbNotifyChannel | None] = mapped_column(
        SAEnum(KtbNotifyChannel, name="ktb_notify_channel", create_type=False),
    )
    notify_contact: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    case_handling: Mapped["CaseHandling"] = relationship(back_populates="ktb_corporate")
    payroll_bank: Mapped["BankName | None"] = relationship(
        foreign_keys=[payroll_bank_name_id],
        lazy="selectin",
    )
    other_bank: Mapped["BankName | None"] = relationship(
        foreign_keys=[other_bank_name_id],
        lazy="selectin",
    )
