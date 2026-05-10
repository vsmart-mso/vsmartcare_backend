"""ภาระการเลี้ยงดู (dependency_loads).

Junction-with-extras ระหว่าง applicants กับ dependency_types
มี composite PK (applicant_id, dependency_type_id)
และฟิลด์ dependency_other_text สำหรับกรณี "อื่น ๆ"
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .applicant import Applicant
    from .lookup import DependencyType


class DependencyLoad(Base):
    __tablename__ = "dependency_loads"

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )

    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id"),
        primary_key=True,
    )
    dependency_type_id: Mapped[int] = mapped_column(
        ForeignKey("dependency_types.id"),
        primary_key=True,
    )

    dependency_other_text: Mapped[str | None] = mapped_column(
        String(500),
        comment="ระบุรายละเอียดเมื่อเลือก dependency แบบ 'อื่น ๆ'",
    )

    applicant: Mapped["Applicant"] = relationship(back_populates="dependency_loads")
    dependency_type: Mapped["DependencyType"] = relationship(lazy="selectin")
