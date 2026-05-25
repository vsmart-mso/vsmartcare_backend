"""ORM models สำหรับ MSO logbook และการส่งข้อมูลออกระบบ.

- MoreMso    1:1 case_handling
- TypeSend   master ประเภทการส่ง
- SendData   N:1 applicants, N:1 type_send
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

from sqlalchemy import Date, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .applicant import Applicant
    from .intake import CaseHandling


class MoreMso(Base):
    """ข้อมูล MSO เพิ่มเติม — 1:1 case_handling"""

    __tablename__ = "more_mso"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    case_handling_id: Mapped[int] = mapped_column(
        ForeignKey("case_handling.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    follow_date: Mapped[str | None] = mapped_column(String(255))
    help_number: Mapped[str | None] = mapped_column(String(255))
    help_date: Mapped[date | None] = mapped_column(Date)
    appove_name: Mapped[str | None] = mapped_column(String(255))
    appove_number: Mapped[str | None] = mapped_column(String(255))
    appove_date: Mapped[date | None] = mapped_column(Date)
    receive_date: Mapped[date | None] = mapped_column(Date)
    cashier: Mapped[str | None] = mapped_column(String(255))
    cashier_name: Mapped[str | None] = mapped_column(String(255))
    follower_name: Mapped[str | None] = mapped_column(String(255))
    follower_position_vsmart_id: Mapped[str | None] = mapped_column(String(255))
    follower_department_vsmart_id: Mapped[str | None] = mapped_column(String(255))
    follower_tel: Mapped[str | None] = mapped_column(String(255))
    follower_date: Mapped[date | None] = mapped_column(Date)
    follower_result: Mapped[str | None] = mapped_column(Text)
    follower_method: Mapped[int | None] = mapped_column(Integer)
    follower_type: Mapped[int | None] = mapped_column(Integer)

    case_handling: Mapped["CaseHandling"] = relationship(back_populates="more_mso")


class TypeSend(Base):
    """master ประเภทการส่งข้อมูล — 1:n send_data"""

    __tablename__ = "type_send"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    detail: Mapped[str | None] = mapped_column(Text)

    send_data_rows: Mapped[list["SendData"]] = relationship(back_populates="type_send")


class SendData(Base):
    """บันทึกการส่งข้อมูลคำร้อง — N:1 applicants, N:1 type_send"""

    __tablename__ = "send_data"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    send_by_sdshv: Mapped[str | None] = mapped_column(String(255))
    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type_send_id: Mapped[int] = mapped_column(
        ForeignKey("type_send.id"),
        nullable=False,
        index=True,
    )
    json_case: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    response_code: Mapped[str | None] = mapped_column(String(255))
    response_text: Mapped[str | None] = mapped_column(Text)

    applicant: Mapped["Applicant"] = relationship(back_populates="send_data_rows")
    type_send: Mapped["TypeSend"] = relationship(
        back_populates="send_data_rows",
        lazy="selectin",
    )
