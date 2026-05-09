"""SQLAlchemy declarative base + naming convention.

Naming convention เป็นกุญแจสำคัญที่ทำให้ Alembic generate migration
ที่อ่านง่ายและ stable ระหว่าง autogenerate รอบต่อ ๆ ไป
(constraint จะมีชื่อแน่นอน ไม่งั้น autogenerate อาจเปลี่ยนชื่อ random ทุกครั้ง)
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class กลางของ ORM models ทั้งระบบ"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
