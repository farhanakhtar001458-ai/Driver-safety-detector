"""Lightweight in-memory rate limiter.

A sliding-window limiter keyed by client identity + route bucket. It is
deliberately dependency-free so the demo works without Redis. In a multi-instance
production deployment the Redis backend should be used instead (see docs).
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._hits: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: Tuple[str, str], limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        now = time.time()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = int(bucket[0] + window_seconds - now) + 1
                return False, retry_after
            bucket.append(now)
            return True, 0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _bucket(path: str) -> str:
    if path.startswith("/api/v1/auth"):
        return "auth"
    if path.startswith("/api/v1/gps"):
        return "gps"
    return "api"


RATE_LIMITS = {"auth": 30, "gps": 1200, "api": settings.RATE_LIMIT_PER_MINUTE}


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in {"OPTIONS", "HEAD"} or not request.url.path.startswith("/api"):
            return await call_next(request)
        if request.url.path.startswith("/api/v1/health"):
            return await call_next(request)
        key = (_client_ip(request), _bucket(request.url.path))
        limit = RATE_LIMITS.get(key[1], settings.RATE_LIMIT_PER_MINUTE)
        allowed, retry_after = limiter.hit(key, limit)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many requests. Please slow down.",
                        "retry_after_seconds": retry_after,
                    },
                },
                headers={"Retry-After": str(retry_after)},
            )
        response: Response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        return response
