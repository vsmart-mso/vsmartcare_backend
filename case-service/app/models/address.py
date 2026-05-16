"""ตาราง `address` — ที่อยู่ของผู้ยื่นคำร้อง.

ผู้ยื่นหนึ่งคนสามารถมีได้หลายที่อยู่ (เช่น ตามทะเบียนบ้าน + ที่อยู่ปัจจุบัน)
แยกประเภทผ่าน FK address_type_id
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base

if TYPE_CHECKING:
    from .applicant import Applicant
    from .geo import SubDistrictPostcode
    from .lookup import AddressType


class Address(Base):
    __tablename__ = "address"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    sub_district_postcode_id: Mapped[int] = mapped_column(
        ForeignKey("sub_districts_postcode.id"),
        nullable=False,
        index=True,
    )
    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("applicants.id"),
        nullable=False,
        index=True,
    )
    address_type_id: Mapped[int] = mapped_column(
        ForeignKey("address_type.id"),
        nullable=False,
    )

    alley: Mapped[str | None] = mapped_column(
        String(255),
        comment="ตรอก",
    )
    sub_lane: Mapped[str | None] = mapped_column(
        String(255),
        comment="ซอย",
    )
    house_name: Mapped[str | None] = mapped_column(String(255))
    road: Mapped[str | None] = mapped_column(String(255))
    house_moo: Mapped[str | None] = mapped_column(String(50))
    house_number: Mapped[str | None] = mapped_column(String(50))
    mobile_phone: Mapped[str | None] = mapped_column(
        String(20),
        comment="เบอร์ติดต่อตามที่อยู่นี้",
    )

    latitude: Mapped[str | None] = mapped_column(String(50))
    longitude: Mapped[str | None] = mapped_column(String(50))

    applicant: Mapped["Applicant"] = relationship(back_populates="addresses")
    sub_district_postcode: Mapped["SubDistrictPostcode"] = relationship(lazy="selectin")
    address_type: Mapped["AddressType"] = relationship(lazy="selectin")
