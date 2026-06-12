"""Admin + การควบคุมเปิด/ปิดบริการรายจังหวัด (TASK-v-care-12062026-01).

- AdminUser: บัญชี admin สำหรับหน้าหลังบ้าน (สมัครผ่าน CLI `app.admin_cli`)
- ProvinceAccessConfig: 1 จังหวัด 1 แถว — is_enabled=false คือปิด (default deny)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base


class AdminUser(Base):
    """บัญชี admin — login แยกจากฝั่งประชาชน (ThaID)."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProvinceAccessConfig(Base):
    """ค่าเปิด/ปิดบริการรายจังหวัด — ไม่มีแถว / is_enabled=false = ปิด."""

    __tablename__ = "province_access_config"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    province_id: Mapped[int] = mapped_column(
        ForeignKey("province.id"), nullable=False, unique=True, index=True
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    updated_by_admin_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_users.id"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    province: Mapped["Province"] = relationship()  # noqa: F821
