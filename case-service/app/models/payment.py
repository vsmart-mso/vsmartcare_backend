"""ข้อมูลอนุมัติและการจ่ายเงินที่ผูกกับ applicants."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .applicant import Applicant
    from .lookup import AttachmentType


class ApproveCase(Base):
    """ประวัติการอนุมัติของคำร้อง"""

    __tablename__ = "approve_case"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id"),
        nullable=False,
        index=True,
    )
    approve_status: Mapped[bool] = mapped_column(default=False, nullable=False)
    esignature: Mapped[str | None] = mapped_column(Text)
    user_sdshv: Mapped[str | None] = mapped_column(String(255))

    applicant: Mapped["Applicant"] = relationship(back_populates="approve_cases")


class WelfareDdaRef(Base):
    """อ้างอิง DDA สำหรับการจ่ายเงิน"""

    __tablename__ = "welfare_dda_ref"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    dda_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    user_sdshv: Mapped[str | None] = mapped_column(String(255))

    welfare_payments: Mapped[list["WelfarePayment"]] = relationship(
        back_populates="welfare_dda_ref",
        cascade="all, delete-orphan",
    )
    file_payments: Mapped[list["FilePayment"]] = relationship(
        back_populates="welfare_dda_ref",
        cascade="all, delete-orphan",
    )


class WelfarePayment(Base):
    """ข้อมูลการจ่ายเงินช่วยเหลือ"""

    __tablename__ = "welfare_payment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id"),
        nullable=False,
        index=True,
    )
    is_037_or_038: Mapped[bool | None] = mapped_column(default=None, nullable=True)
    dda_ref_id: Mapped[int] = mapped_column(
        ForeignKey("welfare_dda_ref.id"),
        nullable=False,
        index=True,
    )
    payment_number: Mapped[str | None] = mapped_column(String(255))
    payment_038_reason: Mapped[str | None] = mapped_column(String(255))
    user_sdshv: Mapped[str | None] = mapped_column(String(255))
    transaction_date: Mapped[date | None] = mapped_column(Date)
    effective_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    applicant: Mapped["Applicant"] = relationship(back_populates="welfare_payments")
    welfare_dda_ref: Mapped["WelfareDdaRef"] = relationship(
        back_populates="welfare_payments",
        lazy="selectin",
    )
    file_payments: Mapped[list["FilePayment"]] = relationship(
        back_populates="welfare_payment",
    )


class FilePayment(Base):
    """ไฟล์แนบสำหรับ DDA ref"""

    __tablename__ = "file_payment"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    welfare_dda_ref_id: Mapped[int] = mapped_column(
        ForeignKey("welfare_dda_ref.id"),
        nullable=False,
        index=True,
    )
    file_original_name: Mapped[str | None] = mapped_column(String(255))
    file_stored_name: Mapped[str | None] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    file_width: Mapped[int | None] = mapped_column(Integer)
    file_height: Mapped[int | None] = mapped_column(Integer)
    attachment_type_id: Mapped[int] = mapped_column(
        ForeignKey("attachment_types.id"),
        nullable=False,
        index=True,
    )
    welfare_payment_id: Mapped[int | None] = mapped_column(
        ForeignKey("welfare_payment.id"),
        nullable=True,
        index=True,
    )

    welfare_dda_ref: Mapped["WelfareDdaRef"] = relationship(
        back_populates="file_payments",
        lazy="selectin",
    )
    welfare_payment: Mapped["WelfarePayment | None"] = relationship(
        back_populates="file_payments",
        lazy="selectin",
    )
    attachment_type: Mapped["AttachmentType"] = relationship(lazy="selectin")
