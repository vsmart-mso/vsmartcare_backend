"""Runtime environment helpers — production guards (CR-05, HI-04, HI-06)."""

from __future__ import annotations

from ..settings import settings


def is_production() -> bool:
    return (settings.app_env or "").strip().lower() in {"production", "prod"}


def require_non_production(action: str) -> None:
    """Raise RuntimeError when a dev-only operation is attempted on production."""
    if is_production():
        raise RuntimeError(f"{action} is disabled when APP_ENV=production")
