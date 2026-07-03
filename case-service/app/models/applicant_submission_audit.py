"""ตาราง `applicant_submission_audit` — snapshot การตัดสินใจ Require KTB ตอนยื่นคำร้อง (1:1 กับ applicants)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .applicant import Applicant


class ApplicantSubmissionAudit(Base):
    __tablename__ = "applicant_submission_audit"

    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    existing_case_source: Mapped[str | None] = mapped_column(String(16))
    existing_case_detected_sources: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    existing_case_ref_id: Mapped[int | None] = mapped_column(Integer)
    existing_case_province_id: Mapped[int | None] = mapped_column(Integer)
    existing_case_province_name: Mapped[str | None] = mapped_column(String(255))
    submission_province_id: Mapped[int | None] = mapped_column(Integer)
    submission_province_name: Mapped[str | None] = mapped_column(String(255))
    is_account_changed: Mapped[bool | None] = mapped_column(Boolean)
    require_ktb_corporate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    require_ktb_reason: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW_CASE")

    applicant: Mapped["Applicant"] = relationship(
        back_populates="submission_audit",
        uselist=False,
    )
