"""สวัสดิการ: ประวัติ, ประเภทที่ขอ, หลักฐานแนบ.

- welfare_histories: สรุปประวัติการรับสวัสดิการ — applicant_id เป็น PK (1:1 กับ applicants)
- welfare_histories_detail: junction ระหว่าง welfare_histories กับ received_welfare_types
- welfare_request_types: junction applicant ↔ request_type
- welfare_evidences: path ไฟล์หลักฐาน
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .applicant import Applicant
    from .lookup import AttachmentType, ReceivedWelfareType, RequestType


class WelfareHistory(Base):
    """ประวัติการรับสวัสดิการ — PK = applicant_id (1:1 กับผู้ยื่น)"""

    __tablename__ = "welfare_histories"

    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id"),
        primary_key=True,
    )

    received_count: Mapped[int | None] = mapped_column(
        comment="จำนวนครั้งที่เคยได้รับ",
    )
    has_received_welfare: Mapped[bool] = mapped_column(default=False, nullable=False)
    total_received_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

    applicant: Mapped["Applicant"] = relationship(back_populates="welfare_history")
    history_details: Mapped[list["WelfareHistoryDetail"]] = relationship(
        back_populates="welfare_history",
        cascade="all, delete-orphan",
    )


class WelfareHistoryDetail(Base):
    """Junction-with-extras: welfare_histories × received_welfare_types"""

    __tablename__ = "welfare_histories_detail"

    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    welfare_history_id: Mapped[int] = mapped_column(
        ForeignKey("welfare_histories.applicant_id"),
        primary_key=True,
    )
    received_welfare_type_id: Mapped[int] = mapped_column(
        ForeignKey("received_welfare_types.id"),
        primary_key=True,
    )

    received_other: Mapped[str | None] = mapped_column(
        String(500),
        comment="ระบุสวัสดิการเพิ่มเติมเมื่อเลือก 'อื่น ๆ'",
    )

    welfare_history: Mapped["WelfareHistory"] = relationship(
        back_populates="history_details",
    )
    received_welfare_type: Mapped["ReceivedWelfareType"] = relationship(lazy="selectin")


class WelfareRequestType(Base):
    """Junction: applicant ↔ request_type"""

    __tablename__ = "welfare_request_types"

    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id"),
        primary_key=True,
    )
    request_type_id: Mapped[int] = mapped_column(
        ForeignKey("request_types.id"),
        primary_key=True,
    )

    request_other_text: Mapped[str | None] = mapped_column(
        String(500),
        comment="ระบุรายละเอียดเพิ่มเติมเมื่อเลือก 'ช่วยเหลือเรื่องอื่นๆ' (request_type_id=3)",
    )
    request_in_kind_text: Mapped[str | None] = mapped_column(
        String(500),
        comment="ระบุรายละเอียดเมื่อเลือก 'ช่วยเหลือเป็นสิ่งของ' (request_type_id=2)",
    )

    applicant: Mapped["Applicant"] = relationship(back_populates="welfare_request_types")
    request_type: Mapped["RequestType"] = relationship(lazy="selectin")


class WelfareEvidence(Base):
    """หลักฐานแนบ (path ไฟล์)"""

    __tablename__ = "welfare_evidences"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    attachment_type_id: Mapped[int] = mapped_column(
        ForeignKey("attachment_types.id"),
        nullable=False,
    )
    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id"),
        nullable=False,
        index=True,
    )

    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    file_original_name: Mapped[str | None] = mapped_column(String(255))
    file_stored_name: Mapped[str | None] = mapped_column(String(255))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    file_width: Mapped[int | None] = mapped_column(Integer)
    file_height: Mapped[int | None] = mapped_column(Integer)
    file_other_type_name: Mapped[str | None] = mapped_column(String(255))

    applicant: Mapped["Applicant"] = relationship(back_populates="welfare_evidences")
    attachment_type: Mapped["AttachmentType"] = relationship(lazy="selectin")
