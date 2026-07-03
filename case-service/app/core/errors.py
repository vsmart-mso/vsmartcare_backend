"""Sanitized HTTP errors for production (ME-04)."""

from __future__ import annotations

from fastapi import HTTPException, status

from .pii import mask_pii_text
from .runtime import is_production


def conflict_from_integrity(exc: Exception, *, code: str = "operation_blocked") -> HTTPException:
    detail: str | dict[str, str]
    if is_production():
        detail = code
    else:
        message = mask_pii_text(str(getattr(exc, "orig", None) or exc))
        detail = {"code": code, "message": message}
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
