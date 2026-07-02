"""In-memory rate limiting (HI-05)."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple sliding-window limiter for auth-sensitive paths."""

    def __init__(
        self,
        app,
        *,
        limit: int = 30,
        window_seconds: int = 60,
        path_prefixes: tuple[str, ...] = (
            "/v1/auth/",
            "/v1/admin/auth/login",
            "/v1/staff/auth/login",
        ),
    ) -> None:
        super().__init__(app)
        self.limit = limit
        self.window = window_seconds
        self.path_prefixes = path_prefixes
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        return forwarded or (request.client.host if request.client else "unknown")

    async def dispatch(self, request: Request, call_next: Callable):
        path = request.url.path
        if not any(path.endswith(p) or p in path for p in self.path_prefixes):
            return await call_next(request)

        now = time.monotonic()
        key = f"{self._client_key(request)}:{path}"
        bucket = self._hits[key]
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= self.limit:
            return JSONResponse({"detail": "rate_limit_exceeded"}, status_code=429)
        bucket.append(now)
        return await call_next(request)
