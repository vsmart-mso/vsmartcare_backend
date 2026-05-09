"""ตาราง screening_logs และ welfare_request_consents — ผูกกับ persons."""

from __future__ import annotations

from datetime import datetime
from typing import Any, TYPE_CHECKING

from sqlalchemy import ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .person import Person


class ScreeningLog(Base):
    __tablename__ = "screening_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    person_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id"),
        nullable=False,
        index=True,
    )

    criteria_version: Mapped[str | None] = mapped_column(String(50))
    screening_result: Mapped[str | None] = mapped_column(String(100))
    failure_reason_code: Mapped[str | None] = mapped_column(String(100))
    screening_status: Mapped[bool] = mapped_column(default=False, nullable=False)
    input_data_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(500))

    person: Mapped["Person"] = relationship(back_populates="screening_logs")


class WelfareRequestConsent(Base):
    __tablename__ = "welfare_request_consents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    person_id: Mapped[int] = mapped_column(
        ForeignKey("persons.id"),
        nullable=False,
        index=True,
    )

    consent_type: Mapped[str | None] = mapped_column(String(100))
    initial_pdpa_accepted: Mapped[bool] = mapped_column(default=False, nullable=False)
    initial_terms_accepted: Mapped[bool] = mapped_column(default=False, nullable=False)
    initial_warning_accepted: Mapped[bool] = mapped_column(default=False, nullable=False)
    final_data_correct_accepted: Mapped[bool] = mapped_column(
        default=False,
        nullable=False,
    )

    person: Mapped["Person"] = relationship(back_populates="consents")
