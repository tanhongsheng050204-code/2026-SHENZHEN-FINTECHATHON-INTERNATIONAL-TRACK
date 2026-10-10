"""A small fixed-window rate limit for the public, unauthenticated endpoints.

The Passport verifier and the lender/auditor share links need no sign-in, so they
are the endpoints someone could hammer to guess links or probe Passport ids. Each
client address gets `per_minute` requests per bucket per minute; more get 429 with
Retry-After.

Authenticated voice input uses the verified tenant/user identity rather than an
address, so changing forwarded headers cannot reset its quota. Other callers keep
the existing address-based behaviour.

On PostgreSQL the count lives in the database (rate_limit_windows), so every API
instance shares one count; identities are stored as keyed hashes, never raw
addresses. Elsewhere (SQLite, tests) or if the database is unreachable, the count
falls back to this process, which still bounds guessing.
"""

import hashlib
import hmac
import threading
import time
from collections.abc import Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy import text

_lock = threading.Lock()
_windows: dict[tuple[str, str], tuple[int, int]] = {}
_UNSET = object()
_store = _UNSET

_HIT = text(
    "insert into public.rate_limit_windows (bucket, identity_hash, minute, hits) "
    "values (:bucket, :identity, :minute, 1) "
    "on conflict (bucket, identity_hash, minute) "
    "do update set hits = rate_limit_windows.hits + 1 returning hits"
)
_PRUNE = text("delete from public.rate_limit_windows where minute < :before")


def configure_store(engine) -> None:
    """Use `engine` for shared counts; None keeps counts in this process."""
    global _store
    _store = engine


def _engine():
    global _store
    if _store is _UNSET:
        from app.db import engine

        _store = engine if engine.dialect.name == "postgresql" else None
    return _store


def _identity_hash(identity: str) -> str:
    from app.config import get_settings

    key = get_settings().token_identity_secret.encode()
    return hmac.new(key, identity.encode(), hashlib.sha256).hexdigest()


def _shared_hits(bucket: str, identity: str, minute: int) -> int | None:
    store = _engine()
    if store is None:
        return None
    try:
        with store.begin() as connection:
            hits = connection.execute(
                _HIT,
                {"bucket": bucket, "identity": _identity_hash(identity), "minute": minute},
            ).scalar_one()
            if hits == 1:
                connection.execute(_PRUNE, {"before": minute - 5})
            return hits
    except Exception:
        # A database hiccup must not open the gate: fall back to this process.
        return None


def _local_hits(bucket: str, identity: str, minute: int) -> int:
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
    return count


def counter(bucket: str, per_minute: int) -> Callable[[str], None]:
    """Count one request for `identity`; raise 429 past `per_minute` this minute."""

    def check(identity: str) -> None:
        minute = int(time.time() // 60)
        count = _shared_hits(bucket, identity, minute)
        if count is None:
            count = _local_hits(bucket, identity, minute)
        if count > per_minute:
            raise HTTPException(
                status_code=429,
                detail="rate_limited",
                headers={"Retry-After": str(60 - int(time.time()) % 60)},
            )

    return check


def client_address(request: Request) -> str:
    # Behind the Vercel proxy and Cloud Run the first forwarded address is the client.
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    return first or (request.client.host if request.client else "unknown")


def limit(bucket: str, per_minute: int, *, per_user: bool = False) -> Callable:
    check = counter(bucket, per_minute)

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
