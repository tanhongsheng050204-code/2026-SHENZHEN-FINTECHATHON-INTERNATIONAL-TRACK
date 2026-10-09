"""A small fixed-window rate limit for the public, unauthenticated endpoints.

The Passport verifier and the lender/auditor share links need no sign-in, so they
are the endpoints someone could hammer to guess links or probe Passport ids. Each
client address gets `per_minute` requests per bucket per minute; more get 429 with
Retry-After.

Authenticated voice input uses the verified tenant/user identity rather than an
address, so changing forwarded headers cannot reset its quota. Other callers keep
the existing address-based behaviour.

The count lives in this process. With several Cloud Run instances the effective
limit is per instance, which still bounds guessing; a shared store (Redis or the
database) would make it exact.
"""

import threading
import time
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request

_lock = threading.Lock()
_windows: dict[tuple[str, str], tuple[int, int]] = {}


def client_address(request: Request) -> str:
    # Behind the Vercel proxy and Cloud Run the first forwarded address is the client.
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    return first or (request.client.host if request.client else "unknown")


def limit(bucket: str, per_minute: int, *, per_user: bool = False) -> Callable:
    def check(identity: str) -> None:
        minute = int(time.time() // 60)
        key = (bucket, identity)
        with _lock:
            window, count = _windows.get(key, (minute, 0))
            if window != minute:
                window, count = minute, 0
            count += 1
            _windows[key] = (window, count)
            if len(_windows) > 50_000:
                for stale in [k for k, (w, _) in _windows.items() if w != minute]:
                    del _windows[stale]
        if count > per_minute:
            raise HTTPException(
                status_code=429,
                detail="rate_limited",
                headers={"Retry-After": str(60 - int(time.time()) % 60)},
            )

    if per_user:
        from app.auth.dependencies import get_current_user
        from app.auth.principal import AuthPrincipal

        def user_dependency(principal: AuthPrincipal = Depends(get_current_user)) -> None:
            check(f"user:{principal.tenant_id}:{principal.user_id}")

        return user_dependency

    def dependency(request: Request) -> None:
        check(client_address(request))

    return dependency


def reset() -> None:
    """For tests."""
    with _lock:
        _windows.clear()
