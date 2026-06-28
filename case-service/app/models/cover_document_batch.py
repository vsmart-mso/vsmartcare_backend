"""ตาราง cover_document_batch — หัวหนังสือนำส่ง 1 ฉบับสำหรับหลายเคส CARE."""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .article import Article


class CoverDocumentBatch(Base):
    __tablename__ = "cover_document_batch"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type_money_id: Mapped[int | None] = mapped_column(
        ForeignKey("type_money_category.id"),
        nullable=True,
        index=True,
    )
    province_id: Mapped[int | None] = mapped_column(
        ForeignKey("province.id"),
        nullable=True,
        index=True,
    )
    approver_sdhsv: Mapped[str | None] = mapped_column(String(64))
    service_vsmart_id: Mapped[str | None] = mapped_column(String(255))
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
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    articles: Mapped[list["Article"]] = relationship(back_populates="cover_document_batch")
