"""Staff accounts for SDSHV workflow (HI-01)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base


class StaffUser(Base):
    """บัญชีเจ้าหน้าที่ — login แยกจากประชาชนและ admin."""

    __tablename__ = "staff_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    province_id: Mapped[int] = mapped_column(
        ForeignKey("province.id"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    province: Mapped["Province"] = relationship()  # noqa: F821


class SecurityAuditLog(Base):
    """Audit trail สำหรับการลบข้อมูลและ ops สำคัญ (CR-05)."""

    __tablename__ = "security_audit_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_cid: Mapped[str | None] = mapped_column(String(13), nullable=True, index=True)
    detail: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
