"""Satisfaction survey — เก็บผลประเมินความพึงพอใจของผู้ยื่นคำขอ."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.base import Base


class SatisfactionSurvey(Base):
    """ผลประเมินความพึงพอใจต่อระบบและการได้รับความช่วยเหลือ."""

    __tablename__ = "satisfaction_surveys"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id"),
        nullable=False,
        index=True,
    )
    # 'system_usage' = ประเมินหลังยื่นฟอร์ม | 'aid_received' = ประเมินหลังเบิกจ่าย
    survey_type: Mapped[str] = mapped_column(String(50), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
