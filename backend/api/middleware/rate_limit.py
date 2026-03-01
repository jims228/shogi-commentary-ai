from __future__ import annotations

import os
import threading
import time
from typing import Dict, List, Tuple, Optional

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


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)) or str(default))
    except Exception:
        return default


# ---- rate-limit rule definition ----

class _Rule:
    """A single path-prefix + method rate-limit rule."""

    __slots__ = ("prefix", "method", "limit")

    def __init__(self, prefix: str, method: str, limit: int):
        self.prefix = prefix
        self.method = method.upper()
        self.limit = limit

    def matches(self, path: str, method: str) -> bool:
        return method == self.method and path.startswith(self.prefix)


class RateLimitMiddleware:
    """In-memory, per-IP fixed-window rate limiter.

    Supports multiple path rules with individual limits.
    Enabled only when at least one rule has limit > 0.
    Designed to be swapped to Redis later.
    """

    def __init__(self, app):
        self.app = app

        self._rules: List[_Rule] = [
            _Rule("/annotate",                "POST", _env_int("RATE_LIMIT_PER_MINUTE", 0)),
            _Rule("/api/analysis/batch",      "POST", _env_int("RATE_LIMIT_BATCH_PER_MINUTE", 5)),
            _Rule("/api/explain/digest",      "POST", _env_int("RATE_LIMIT_LLM_PER_MINUTE", 10)),
            _Rule("/api/explain",             "POST", _env_int("RATE_LIMIT_LLM_PER_MINUTE", 10)),
        ]
        # Drop disabled rules (limit <= 0)
        self._rules = [r for r in self._rules if r.limit > 0]

        self._lock = threading.Lock()
        # (ip, rule_prefix) -> (window_start_epoch_sec, count)
        self._state: Dict[Tuple[str, str], Tuple[int, int]] = {}

    def _match(self, path: str, method: str) -> Optional[_Rule]:
        for rule in self._rules:
            if rule.matches(path, method):
                return rule
        return None

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or not self._rules:
            return await self.app(scope, receive, send)

        path = scope.get("path") or ""
        method = (scope.get("method") or "").upper()

        rule = self._match(path, method)
        if rule is None:
            return await self.app(scope, receive, send)

        ip = _get_client_ip(scope)
        now = int(time.time())
        window_start = now - (now % 60)
        key = (ip, rule.prefix)

        with self._lock:
            prev = self._state.get(key)
            if prev is None or prev[0] != window_start:
                self._state[key] = (window_start, 1)
                allowed = True
            else:
                count = prev[1] + 1
                self._state[key] = (window_start, count)
                allowed = count <= rule.limit

        if allowed:
            return await self.app(scope, receive, send)

        res = JSONResponse(
            {"detail": "Rate limit exceeded"},
            status_code=429,
            headers={"Retry-After": str((window_start + 60) - now)},
        )
        return await res(scope, receive, send)
