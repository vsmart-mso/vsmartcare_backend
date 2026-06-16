"""Async engine + session สำหรับ dashboard-service.

ต่อ DB เดียวกับ case-service (asyncpg + SQLAlchemy 2.x async) แบบ **อ่านอย่างเดียว**
service นี้ไม่มี Alembic และไม่เขียนข้อมูลใด ๆ ลง DB — session จึงไม่ต้อง commit/rollback
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ..settings import settings

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
)

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yield AsyncSession อ่านอย่างเดียว (ไม่ commit)."""
    async with SessionLocal() as session:
        yield session
