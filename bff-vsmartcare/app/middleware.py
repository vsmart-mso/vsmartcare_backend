"""Request-scoped auth forwarding + security middleware for BFF."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .settings import internal_api_key, is_production, settings

_forward_auth: ContextVar[Optional[str]] = ContextVar("_forward_auth", default=None)


def get_forward_auth_header() -> Optional[str]:
    return _forward_auth.get()


def merge_forward_headers(
    headers: Optional[dict[str, str]] = None,
    *,
    inject_internal_api_key: bool = False,
) -> dict[str, str]:
    """Merge explicit headers with captured Authorization; never forward client X-API-Key (CR-02)."""
    merged = dict(headers or {})
    auth = get_forward_auth_header()
    if auth and "Authorization" not in merged:
        merged["Authorization"] = auth
    merged.pop("X-API-Key", None)
    if inject_internal_api_key:
        key = internal_api_key()
        if key:
            merged["X-API-Key"] = key
    elif "Authorization" not in merged or not str(merged.get("Authorization", "")).strip():
        key = internal_api_key()
        if key:
            merged["X-API-Key"] = key
    return merged


class CaptureAuthMiddleware(BaseHTTPMiddleware):
    """Capture Bearer for downstream forward only — strip client X-API-Key."""

    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("authorization")
        auth_token = _forward_auth.set(auth)
        try:
            return await call_next(request)
        finally:
            _forward_auth.reset(auth_token)


_STAFF_COMPAT_PATH_PREFIXES = (
    "/v1/case_for_staff",
    "/v1/intake",
    "/v1/lookups",
    "/v1/geo",
    "/v1/dashboard",
)


class StaffRouteAuthMiddleware(BaseHTTPMiddleware):
    """Require Bearer or trusted X-API-Key on staff/intake/lookup/geo/dashboard proxy paths."""

    async def dispatch(self, request: Request, call_next):
        prefix = settings.bff_api_prefix.rstrip("/")
        path = request.url.path
        if prefix and path.startswith(prefix):
            rel = path[len(prefix) :]
        else:
            rel = path
        if any(rel.startswith(p) for p in _STAFF_COMPAT_PATH_PREFIXES):
            auth = (request.headers.get("authorization") or "").strip()
            api_key = (request.headers.get("x-api-key") or "").strip()
            expected_api_key = (settings.bff_api_password or "").strip()
            has_valid_api_key = bool(expected_api_key) and api_key == expected_api_key
            has_bearer = auth.lower().startswith("bearer ")
            if not has_bearer and not has_valid_api_key:
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
        if is_production():
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        return response
