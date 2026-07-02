"""Request-scoped auth forwarding + security middleware for BFF."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .settings import settings

_forward_auth: ContextVar[Optional[str]] = ContextVar("_forward_auth", default=None)


def get_forward_auth_header() -> Optional[str]:
    return _forward_auth.get()


def merge_forward_headers(headers: Optional[dict[str, str]] = None) -> dict[str, str]:
    merged = dict(headers or {})
    auth = get_forward_auth_header()
    if auth and "Authorization" not in merged:
        merged["Authorization"] = auth
    return merged


class CaptureAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("authorization")
        token = _forward_auth.set(auth)
        try:
            return await call_next(request)
        finally:
            _forward_auth.reset(token)


class StaffRouteAuthMiddleware(BaseHTTPMiddleware):
    """Require Bearer token on staff/intake proxy paths (HI-01)."""

    async def dispatch(self, request: Request, call_next):
        prefix = settings.bff_api_prefix.rstrip("/")
        path = request.url.path
        if prefix and path.startswith(prefix):
            rel = path[len(prefix) :]
        else:
            rel = path
        if rel.startswith("/v1/case_for_staff") or rel.startswith("/v1/intake"):
            auth = (request.headers.get("authorization") or "").strip()
            if not auth.lower().startswith("bearer "):
                return JSONResponse({"detail": "missing_bearer_token"}, status_code=401)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """ME-03 — baseline security headers on BFF responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        if settings.app_env.strip().lower() in {"production", "prod"}:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response
