"""OCR Result model — เชื่อม applicant_id ไปยัง applicants.id (FK จริง)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OcrResult(Base):
    __tablename__ = "ocr_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # FK จริงไปยัง applicants.id (database เดียวกัน)
    applicant_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("applicants.id", ondelete="SET NULL"), index=True, nullable=True
    )

    target_name_checked: Mapped[str] = mapped_column(Text, nullable=False)
    pre_file: Mapped[str] = mapped_column(String(255), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, default="")

    # bank_info
    account_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    account_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    deposit_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    branch_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    match_status: Mapped[str] = mapped_column(String(20), nullable=False, default="no_text")
    fuzzy_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
