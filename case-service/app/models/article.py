"""ตาราง article — เนื้อหาบทความ/รายงาน 1:1 กับ applicants."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .applicant import Applicant
    from .cover_document_batch import CoverDocumentBatch
    from .payment import ApproveCase


class Article(Base):
    """เนื้อหาบทความที่ผูกกับคำร้องหนึ่งรายการ (1:1)."""

    __tablename__ = "article"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("cover_document_batch.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    service_vsmart_id: Mapped[str | None] = mapped_column(String(255))
    approver_sdhsv_id: Mapped[str | None] = mapped_column(String(64))
    phone_service: Mapped[str | None] = mapped_column(String(255))
    at: Mapped[str | None] = mapped_column(String(255))
    date_at: Mapped[date | None] = mapped_column(Date)
    title: Mapped[str | None] = mapped_column(String(255))
    director_vsmart_id: Mapped[str | None] = mapped_column(
        "refer_vsmart_id",
        String(255),
    )
    original_story: Mapped[str | None] = mapped_column(Text)
    fact_story: Mapped[str | None] = mapped_column(Text)
    laws: Mapped[str | None] = mapped_column(Text)
    consider: Mapped[str | None] = mapped_column(Text)
    suggestion: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    applicant: Mapped["Applicant"] = relationship(back_populates="article", uselist=False)
    cover_document_batch: Mapped["CoverDocumentBatch | None"] = relationship(back_populates="articles")
    approve_cases: Mapped[list["ApproveCase"]] = relationship(back_populates="article")
