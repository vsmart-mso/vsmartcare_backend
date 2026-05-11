"""Async engine + session factory สำหรับ case-service.

ใช้ asyncpg เป็น driver และ create_async_engine ของ SQLAlchemy 2.x
expire_on_commit=False ป้องกันปัญหา attribute expiration หลัง commit
ใน async context (เป็น pattern แนะนำของ SQLAlchemy ใน FastAPI)
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
    """FastAPI dependency: yield AsyncSession ที่ commit/rollback อัตโนมัติเมื่อ request จบ"""
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
