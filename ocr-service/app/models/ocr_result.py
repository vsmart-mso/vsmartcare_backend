"""SQLAlchemy model สำหรับ ocr_results — เก็บผล OCR ที่โยงกับ applicant_id (ใบคำร้อง)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OcrResult(Base):
    __tablename__ = "ocr_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK concept ไปยัง case-service.applicant.id (nullable — ผูกทีหลังได้เมื่อมี applicant_id)
    applicant_id: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)

    target_name_checked: Mapped[str] = mapped_column(Text, nullable=False)
    pre_file: Mapped[str] = mapped_column(String(255), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, default="")

    # bank_info
    account_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    match_status: Mapped[str] = mapped_column(String(20), nullable=False, default="no_text")
    fuzzy_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
