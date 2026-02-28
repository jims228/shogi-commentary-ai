from __future__ import annotations

import os
import threading
import time
from typing import Dict, Tuple, Optional

from starlette.responses import JSONResponse


def _get_first_header(scope_headers, name_lower: bytes) -> Optional[str]:
    for k, v in scope_headers or []:
        if k.lower() == name_lower:
            try:
                return v.decode("utf-8")
            except Exception:
                return None
    return None


def _get_client_ip(scope) -> str:
    headers = scope.get("headers") or []
    xff = _get_first_header(headers, b"x-forwarded-for")
    if xff:
        # X-Forwarded-For: client, proxy1, proxy2 ...
        return (xff.split(",")[0] or "").strip() or "unknown"

    client = scope.get("client")
    if client and isinstance(client, (list, tuple)) and len(client) >= 1:
        return str(client[0])

    return "unknown"


class RateLimitMiddleware:
    """In-memory, per-IP fixed-window rate limiter for /annotate.

    Enabled only when RATE_LIMIT_PER_MINUTE > 0.
    Designed to be swapped to Redis later.
    """

    def __init__(self, app):
        self.app = app
        try:
            self.limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "0") or "0")
        except Exception:
            self.limit = 0

        self._lock = threading.Lock()
        # ip -> (window_start_epoch_sec, count)
        self._state: Dict[str, Tuple[int, int]] = {}

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or self.limit <= 0:
            return await self.app(scope, receive, send)

        path = scope.get("path") or ""
        method = (scope.get("method") or "").upper()

        if not path.startswith("/annotate") or method != "POST":
            return await self.app(scope, receive, send)

        ip = _get_client_ip(scope)
        now = int(time.time())
        window_start = now - (now % 60)

        with self._lock:
            prev = self._state.get(ip)
            if prev is None or prev[0] != window_start:
                self._state[ip] = (window_start, 1)
                allowed = True
            else:
                count = prev[1] + 1
                self._state[ip] = (window_start, count)
                allowed = count <= self.limit

        if allowed:
            return await self.app(scope, receive, send)

        res = JSONResponse(
            {"detail": "Rate limit exceeded"},
            status_code=429,
            headers={"Retry-After": str((window_start + 60) - now)},
        )
        return await res(scope, receive, send)
