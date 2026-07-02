"""Audit logging for security-sensitive operations (CR-05)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.pii import mask_cid
from ..models.staff import SecurityAuditLog


async def write_audit_log(
    session: AsyncSession,
    *,
    action: str,
    actor_type: str,
    actor_id: str,
    target_cid: str | None = None,
    detail: str | None = None,
) -> None:
    session.add(
        SecurityAuditLog(
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            target_cid=mask_cid(target_cid) if target_cid else None,
            detail=detail,
        )
    )
