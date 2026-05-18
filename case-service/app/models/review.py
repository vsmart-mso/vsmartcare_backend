"""Review field master data + welfare review comments."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .status_log import WelfareRequestStatus


class ReviewField(Base):
    """หัวข้อที่สามารถส่งกลับแก้ไขได้ (master data)"""

    __tablename__ = "review_field"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    step: Mapped[int] = mapped_column(Integer, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    comments: Mapped[list["WelfareReviewComment"]] = relationship(
        back_populates="review_field"
    )


class WelfareReviewComment(Base):
    """Comment ต่อหัวข้อต่อการส่งกลับแก้ไข 1 ครั้ง (junction)"""

    __tablename__ = "welfare_review_comment"
    __table_args__ = (
        UniqueConstraint(
            "welfare_request_status_id",
            "review_field_id",
            name="uq_welfare_review_comment_status_field",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    welfare_request_status_id: Mapped[int] = mapped_column(
        ForeignKey("welfare_request_status.id"),
        nullable=False,
        index=True,
    )
    review_field_id: Mapped[int] = mapped_column(
        ForeignKey("review_field.id"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    welfare_request_status: Mapped["WelfareRequestStatus"] = relationship(
        back_populates="review_comments"
    )
    review_field: Mapped["ReviewField"] = relationship(back_populates="comments")
