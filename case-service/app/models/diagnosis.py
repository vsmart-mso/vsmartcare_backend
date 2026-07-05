"""คำวินิจฉัยของเจ้าหน้าที่ (multi-user) — หน้า 11 รับเรื่อง.

ตารางใน migration 0070:
  - CaseDiagnosis            (คำวินิจฉัย 1:N applicants — 1 แถวต่อ user ต่อเคส)
  - CaseDiagnosisEditHistory (ประวัติการแก้ไขคำวินิจฉัย BR-DIAG-06)

แยกจาก case_regulation_choice.comment (1:1 legacy) — ผูกกับ applicant ตรง ๆ
เพื่อให้เพิ่มคำวินิจฉัยได้ก่อนที่ case_handling จะถูกสร้าง
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .applicant import Applicant


class CaseDiagnosis(Base):
    """คำวินิจฉัยของเจ้าหน้าที่ 1 คนต่อ 1 เคส — ownership ผูกกับ owner_user_id (VSmart)"""

    __tablename__ = "case_diagnosis"
    __table_args__ = (
        UniqueConstraint("applicant_id", "owner_user_id", name="uq_case_diagnosis_applicant_owner"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    diagnosis_text: Mapped[str] = mapped_column(Text, nullable=False)

    # owner_user_id = Django request.user.id ฝั่ง VSmart (กุญแจ ownership)
    # 0 = แถวที่ migrate มาจาก comment เดิม (ไม่ทราบเจ้าของ — read-only ถาวร)
    owner_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # snapshot ณ เวลาบันทึก — ไม่ FK เพราะข้อมูลเจ้าหน้าที่อยู่คนละระบบ (VSmart)
    owner_sdshv: Mapped[str | None] = mapped_column(String(255))
    owner_name: Mapped[str | None] = mapped_column(String(255))
    owner_position: Mapped[str | None] = mapped_column(String(255))
    owner_organization: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )

    applicant: Mapped["Applicant"] = relationship()
    edit_histories: Mapped[list["CaseDiagnosisEditHistory"]] = relationship(
        back_populates="diagnosis",
        cascade="all, delete-orphan",
        order_by="CaseDiagnosisEditHistory.created_at.desc()",
    )


class CaseDiagnosisEditHistory(Base):
    """ประวัติการแก้ไขคำวินิจฉัย — insert 1 แถวทุกครั้งที่ PATCH (BR-DIAG-06)"""

    __tablename__ = "case_diagnosis_edit_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    diagnosis_id: Mapped[int] = mapped_column(
        ForeignKey("case_diagnosis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    old_text: Mapped[str] = mapped_column(Text, nullable=False)
    new_text: Mapped[str] = mapped_column(Text, nullable=False)
    edit_reason: Mapped[str | None] = mapped_column(Text)
    edited_by_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    edited_by_name: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    diagnosis: Mapped["CaseDiagnosis"] = relationship(back_populates="edit_histories")
