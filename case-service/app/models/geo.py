"""ที่อยู่/ภูมิศาสตร์: จังหวัด → อำเภอ → ตำบล + รหัสไปรษณีย์.

โครงสร้างตาม ER:
  province (1) ─< districts (N)
  districts (1) ─< sub_districts (N)
  sub_districts (M) ─── sub_districts_postcode ─── (M) postcode

sub_districts_postcode เป็น bridge table เพราะ ER ระบุ M:N
(ตำบลเดียวอาจมีได้หลายรหัสไปรษณีย์ และรหัสเดียวอาจครอบหลายตำบล)
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.base import Base


class Province(Base):
    """จังหวัด"""

    __tablename__ = "province"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str | None] = mapped_column(String(10), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    districts: Mapped[list["District"]] = relationship(
        back_populates="province",
        cascade="all, delete-orphan",
    )


class District(Base):
    """อำเภอ"""

    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str | None] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    province_id: Mapped[int] = mapped_column(
        ForeignKey("province.id"),
        nullable=False,
        index=True,
    )

    province: Mapped["Province"] = relationship(back_populates="districts")
    sub_districts: Mapped[list["SubDistrict"]] = relationship(
        back_populates="district",
        cascade="all, delete-orphan",
    )


class SubDistrict(Base):
    """ตำบล"""

    __tablename__ = "sub_districts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str | None] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    district_id: Mapped[int] = mapped_column(
        ForeignKey("districts.id"),
        nullable=False,
        index=True,
    )

    district: Mapped["District"] = relationship(back_populates="sub_districts")
    sub_district_postcodes: Mapped[list["SubDistrictPostcode"]] = relationship(
        back_populates="sub_district",
        cascade="all, delete-orphan",
    )


class Postcode(Base):
    """รหัสไปรษณีย์"""

    __tablename__ = "postcode"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    sub_district_postcodes: Mapped[list["SubDistrictPostcode"]] = relationship(
        back_populates="postcode",
    )


class SubDistrictPostcode(Base):
    """Bridge table: เชื่อม sub_district กับ postcode (M:N).

    มี surrogate id เป็น PK เพราะ ER กำหนดเป็น id-based bridge
    (ทำให้ FK จากตาราง address ผูกผ่าน id เดียวสะดวก)
    """

    __tablename__ = "sub_districts_postcode"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sub_district_id: Mapped[int] = mapped_column(
        ForeignKey("sub_districts.id"),
        nullable=False,
        index=True,
    )
    postcode_id: Mapped[int] = mapped_column(
        ForeignKey("postcode.id"),
        nullable=False,
        index=True,
    )

    sub_district: Mapped["SubDistrict"] = relationship(
        back_populates="sub_district_postcodes",
    )
    postcode: Mapped["Postcode"] = relationship(
        back_populates="sub_district_postcodes",
    )
