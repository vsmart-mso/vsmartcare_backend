"""Timeline การแก้ไขข้อมูลคำร้องโดยนักสังคมฯ — แยกจาก welfare_request_status."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .applicant import Applicant
    from .lookup import CurrentStatus


class CaseDataEditLog(Base):
    __tablename__ = "case_data_edit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    current_status_id_at_edit: Mapped[int] = mapped_column(
        ForeignKey("current_status.id"),
        nullable=False,
    )

    edit_by_sdshv: Mapped[str | None] = mapped_column(String(255))
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sections: Mapped[str | None] = mapped_column(String(32))
    remarks: Mapped[str | None] = mapped_column(Text)

    applicant: Mapped["Applicant"] = relationship(back_populates="data_edit_logs")
    current_status_at_edit: Mapped["CurrentStatus"] = relationship(lazy="selectin")
