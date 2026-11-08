"""Sliding-window rate limits for authentication endpoints (per client address and per account).

In-process: correct for the single API process this build runs. Several API workers need a shared store (Redis) —
listed as planned in docs/security.md. The per-account lockout (5 failures) and the OTP send cap stay in the database.
"""
from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import HTTPException, Request

from .config import get_settings

_hits: dict[str, deque] = {}
_lock = threading.Lock()


def reset() -> None:
    with _lock:
        _hits.clear()


def client_ip(request: Request) -> str:
    # Behind the reverse proxy the real address is the first X-Forwarded-For hop; only trusted when configured.
    if get_settings().trust_proxy:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check(key: str, limit: int, window_s: int) -> None:
    now = time.monotonic()
    with _lock:
        q = _hits.setdefault(key, deque())
        while q and q[0] <= now - window_s:
            q.popleft()
        if len(q) >= limit:
            retry = int(window_s - (now - q[0])) + 1
            raise HTTPException(429, "too many attempts; wait and try again", headers={"Retry-After": str(retry)})
        q.append(now)


def auth_limit(request: Request, what: str, account: str | None = None) -> None:
    s = get_settings()
    limit, window = {"login": (s.rate_login_per_min, 60), "otp": (s.rate_otp_per_5min, 300), "link": (s.rate_link_per_min, 60)}[what]
    check(f"{what}:ip:{client_ip(request)}", limit, window)
    if account:
        check(f"{what}:acct:{account.strip().lower()[:120]}", limit, window)
