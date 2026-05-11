"""Async DB engine สำหรับบันทึก persons — ใช้เมื่อตั้ง DATABASE_URL เท่านั้น."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio.session import AsyncSession

_engine: Optional[AsyncEngine] = None
SessionLocal: Optional[async_sessionmaker[AsyncSession]] = None


def is_database_configured() -> bool:
    """อ่านค่าหลัง configure_database — อย่า `from db import SessionLocal` แล้วเช็กทิ้งไว้ (จะค้าง None)."""
    return SessionLocal is not None


def configure_database(database_url: str) -> None:
    global _engine, SessionLocal
    if _engine is not None:
        return
    url = (database_url or "").strip()
    if not url:
        SessionLocal = None
        return
    _engine = create_async_engine(url, pool_pre_ping=True, future=True)
    SessionLocal = async_sessionmaker(_engine, expire_on_commit=False, autoflush=False)


async def shutdown_database() -> None:
    global _engine, SessionLocal
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    SessionLocal = None
