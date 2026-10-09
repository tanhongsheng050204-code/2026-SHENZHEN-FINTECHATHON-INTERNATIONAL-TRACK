"""The daily briefing: what needs this person today, from their own records and role.

In the app it may name exact amounts to the roles that read the cash pages (the
same rule as position workspaces). Pushed by email or Telegram it carries only
ranges and counts plus a prompt to sign in, because a message can be forwarded.
"""

import datetime as dt

from sqlalchemy import func, select

from app import models
from app.auth.principal import AuthPrincipal
from app.contracts.assistant import Briefing, BriefingLine
from app.schemas import UserRole
from app.services import cashflow, cashflow_engine, external_grants
from app.services.live_agents import _sees_exact

_CASH_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)
_OVERSIGHT = (UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)
_DATA_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR)
_STALE_DAYS = 7


def _when(days: int) -> str:
    if days < 7:
        return "this week"
    if days < 14:
        return "next week"
    return f"in about {round(days / 7)} weeks"


def _inbox_line(db, principal: AuthPrincipal, exact: bool) -> BriefingLine:
    from app.services.assistant import _inbox

    mine = [a for a in _inbox(db, principal) if a.can_decide]
    if not mine:
        return BriefingLine(kind="inbox", text="Nothing is waiting for you.", screen="inbox")
    count = len(mine)
    first = ", ".join(a.title for a in mine[:2]) if exact else ""
    return BriefingLine(
        kind="inbox",
        text=f"{count} item{'s' if count != 1 else ''} waiting for you"
        + (f": {first}{'…' if count > 2 else '.'}" if first else "."),
        screen="inbox",
        tone="attention",
    )


def _cash_line(db, principal: AuthPrincipal, exact: bool) -> BriefingLine | None:
    if principal.role not in _CASH_ROLES:
        return None
    today = dt.date.today()
    basis = cashflow.basis_for(db, principal, today)
    forecast = cashflow_engine.build_forecast(basis, horizon_days=90, as_of=today)
    shortfall = forecast.shortfall
    if shortfall is None:
        return BriefingLine(
            kind="cash", text="Cash stays above your minimum for 90 days.", screen="cashflow"
        )
    if exact:
        text = (
            f"Cash falls below your minimum on day {shortfall.day} "
            f"({shortfall.date:%d %b}): a gap of RM{shortfall.gap:,.2f}."
        )
    else:
        text = f"Cash is expected to fall below your minimum {_when(shortfall.day)}."
    return BriefingLine(kind="cash", text=text, screen="cashflow", tone="risk")


def _sharing_line(db, principal: AuthPrincipal) -> BriefingLine | None:
    if db is None or principal.role != UserRole.OWNER_DIRECTOR:
        return None
    soon = dt.datetime.now(dt.UTC) + dt.timedelta(days=2)
    tenant_id = str(principal.tenant_id)
    expiring = [
        grant
        for grant, _ in external_grants._replay(
            external_grants._events(db, tenant_id=tenant_id), external_grants._now()
        ).values()
        if grant.status == "active" and grant.expires_at <= soon
    ]
    if not expiring:
        return None
    count = len(expiring)
    return BriefingLine(
        kind="sharing",
        text=f"{count} lender or auditor link{'s' if count != 1 else ''} "
        "will expire within 2 days.",
        screen="financing",
        tone="attention",
    )


def _guardrail_line(db, principal: AuthPrincipal) -> BriefingLine | None:
    event = getattr(models, "SecurityGuardrailEvent", None)
    if db is None or event is None or principal.role not in _OVERSIGHT:
        return None
    since = dt.datetime.now(dt.UTC) - dt.timedelta(days=1)
    count = db.scalar(
        select(func.count()).where(
            event.tenant_id == str(principal.tenant_id), event.occurred_at >= since
        )
    )
    if not count:
        return None
    return BriefingLine(
        kind="guardrails",
        text=f"The guardrails stopped {count} thing{'s' if count != 1 else ''} in the last day.",
        screen="trust",
        tone="attention",
    )


def _data_line(db, principal: AuthPrincipal) -> BriefingLine | None:
    batch = getattr(models, "BusinessImportBatch", None)
    if db is None or batch is None or principal.role not in _DATA_ROLES:
        return None
    latest = db.scalar(
        select(func.max(batch.created_at)).where(batch.tenant_id == str(principal.tenant_id))
    )
    if latest is None:
        return None
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=dt.UTC)
    age = (dt.datetime.now(dt.UTC) - latest).days
    if age < _STALE_DAYS:
        return None
    return BriefingLine(
        kind="data",
        text=f"Your records were last imported {age} days ago; the forecast may be out of date.",
        screen="ingestion",
        tone="attention",
    )


def build(db, principal: AuthPrincipal, *, exact: bool | None = None) -> Briefing:
    exact = _sees_exact(principal) if exact is None else exact
    lines = [
        line
        for line in (
            _cash_line(db, principal, exact),
            _inbox_line(db, principal, exact),
            _sharing_line(db, principal),
            _guardrail_line(db, principal),
            _data_line(db, principal),
        )
        if line is not None
    ]
    return Briefing(greeting="Here is what needs you today.", lines=lines)


def push_text(db, principal: AuthPrincipal) -> str:
    """The pushed version: ranges and counts only, then a prompt to sign in."""
    briefing = build(db, principal, exact=False)
    body = "\n".join(f"• {line.text}" for line in briefing.lines)
    return f"DuitDuit morning briefing\n\n{body}\n\nSign in to DuitDuit for the details."
