"""Log การเปลี่ยนสถานะคำร้อง — ตาราง welfare_request_status."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .applicant import Applicant
    from .lookup import CurrentStatus
    from .review import WelfareReviewComment


class WelfareRequestStatus(Base):
    __tablename__ = "welfare_request_status"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id"),
        nullable=False,
        index=True,
    )
    current_status_id: Mapped[int] = mapped_column(
        ForeignKey("current_status.id"),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    update_by_sdshv: Mapped[str | None] = mapped_column(String(255))

    remarks: Mapped[str | None] = mapped_column(Text)

    applicant: Mapped["Applicant"] = relationship(back_populates="status_logs")
    current_status: Mapped["CurrentStatus"] = relationship(lazy="selectin")
    review_comments: Mapped[list["WelfareReviewComment"]] = relationship(
        back_populates="welfare_request_status"
    )
