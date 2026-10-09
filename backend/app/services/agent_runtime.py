"""Supervisor and agent runs over the company's cash data.

The Supervisor routes a goal to the agents whose skills fit it, using fixed keyword
rules in English, Malay and Chinese (no language model, so a run is repeatable and
explainable). Each agent then calls a real tool on the tenant's cash basis (its
imported records, or the synthetic demo company): the cash-flow engine's forecast,
a what-if scenario over receivables, and the financing rules over the tenant's
profile. Every message in the stream is built from those results. For the demo
company, proposals point at the sample review inbox items that hold the same work;
for a tenant on its own records each proposal is saved to the persisted review
inbox (app.services.review_inbox), once: a repeated run reuses the open item.

A run is stateless: its id carries the goal and an HMAC binding it to the tenant
and the person who started it, so any instance can stream it and nobody else can.
Every tool call is checked against the agent's manifest (available, read/draft
only) and, where Plan 2's guardrails are deployed, its kill switch and budget.
"""

import base64
import datetime as dt
import hashlib
import hmac
import re
from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException

from app.auth.principal import AuthPrincipal
from app.config import get_settings
from app.contracts.agents import AgentRunCreated, AgentRunEvent
from app.contracts.cashflow import CashSignal, EventShift, ForecastResponse
from app.contracts.common import DataMode, EvidenceRef
from app.services import cashflow, cashflow_engine, financing_profile, review_inbox
from app.stubs import agents as manifests
from app.stubs.financing import matches

HORIZON_DAYS = 90
_RUN_ID = re.compile(r"^run_([A-Za-z0-9_-]{1,700})\.([0-9a-f]{32})$")

_CASH = (
    "cash",
    "payroll",
    "salary",
    "salaries",
    "shortfall",
    "runway",
    "forecast",
    "balance",
    "afford",
    "cover",
    "bills",
    "gaji",
    "tunai",
    "现金",
    "工资",
    "薪",
    "资金",
)
_COLLECT = (
    "overdue",
    "receivable",
    "receivables",
    "collect",
    "collection",
    "collections",
    "late",
    "remind",
    "reminder",
    "reminders",
    "unpaid",
    "owe",
    "owes",
    "invoice",
    "invoices",
    "hutang",
    "tertunggak",
    "逾期",
    "应收",
    "催",
)
_FINANCE = (
    "loan",
    "loans",
    "financing",
    "borrow",
    "credit",
    "capital",
    "pinjaman",
    "pembiayaan",
    "贷款",
    "融资",
)

# Review inbox items that hold each proposal for a person to decide.
_INBOX = {
    "cashflow": "act_cashflow_alert",
    "receivables": "act_reminders",
    "financing": "act_financing_pack",
}


def _ringgit(amount: Decimal) -> str:
    return f"RM{amount:,.2f}"


def _mentions(goal: str, words: tuple[str, ...]) -> bool:
    text = goal.casefold()
    for word in words:
        if word.isascii():
            if re.search(rf"\b{re.escape(word)}\b", text):
                return True
        elif word in text:
            return True
    return False


@dataclass(frozen=True)
class Plan:
    cash: bool
    collections: bool
    financing: bool

    @property
    def empty(self) -> bool:
        return not (self.cash or self.collections or self.financing)


def plan(goal: str) -> Plan:
    return Plan(
        cash=_mentions(goal, _CASH),
        collections=_mentions(goal, _COLLECT),
        financing=_mentions(goal, _FINANCE),
    )


def _external_guard(db, *, tenant_id: str, agent_id: str, skill_id: str, side_effect: str):
    """Plan 2's persistent kill switch and daily budget, once that module is deployed."""
    try:
        from app.security.guardrails import authorize_tool
    except ImportError:
        return
    authorize_tool(
        db, tenant_id=tenant_id, agent_id=agent_id, skill_id=skill_id, side_effect=side_effect
    )
    # Persist the reservation before invoking the tool. A read-only run or a
    # subsequent tool failure must not roll back earlier budget charges.
    db.commit()


def authorize(db, principal: AuthPrincipal, agent_id: str, skill_id: str) -> None:
    try:
        agent = manifests.find_agent(agent_id)
    except LookupError as error:
        raise HTTPException(403, "tool_not_allowed") from error
    skill = next((s for s in agent.skills if s.id == skill_id), None)
    if (
        agent.build_status != "built"
        or skill is None
        or skill.availability != "available"
        or skill.side_effect not in ("read", "draft")
    ):
        raise HTTPException(403, "tool_not_allowed")
    _external_guard(
        db,
        tenant_id=str(principal.tenant_id),
        agent_id=agent_id,
        skill_id=skill_id,
        side_effect=skill.side_effect,
    )


def _mac(principal: AuthPrincipal, goal: str) -> str:
    key = get_settings().token_root_secret.encode()
    message = f"agent-run|{principal.tenant_id}|{principal.user_id}|{goal}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()[:32]


def start_run(db, principal: AuthPrincipal, goal: str) -> AgentRunCreated:
    authorize(db, principal, "supervisor", "route_goal")
    encoded = base64.urlsafe_b64encode(goal.encode()).decode().rstrip("=")
    run_id = f"run_{encoded}.{_mac(principal, goal)}"
    return AgentRunCreated(
        data_mode=DataMode.STUB, run_id=run_id, events_url=f"/agents/runs/{run_id}/events"
    )


def goal_for(principal: AuthPrincipal, run_id: str) -> str:
    match = _RUN_ID.match(run_id)
    if match is None:
        raise LookupError(run_id)
    encoded, mac = match.groups()
    try:
        goal = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    except ValueError as error:
        raise LookupError(run_id) from error
    if not hmac.compare_digest(mac, _mac(principal, goal)):
        raise LookupError(run_id)
    return goal


def _invoice_name(label: str) -> str:
    # Demo labels start with the invoice number; live labels carry no name, only a date.
    name = label.split(" · ")[0]
    return "the i" + name[1:] if name.startswith("Invoice ") else name


def _early_receivables(forecast: ForecastResponse) -> list[CashSignal]:
    """The fewest receivables landing after the shortfall whose total covers its gap."""
    shortfall = forecast.shortfall
    if shortfall is None:
        return []
    later = sorted(
        (
            s
            for s in forecast.drivers
            if s.source_agent == "receivables"
            and s.kind == "inflow"
            and s.likely_day is not None
            and s.likely_day > shortfall.day
        ),
        key=lambda s: (s.likely_day, s.id),
    )
    chosen: list[CashSignal] = []
    for signal in later[:3]:
        chosen.append(signal)
        if sum((s.amount_myr for s in chosen), Decimal("0")) >= shortfall.gap:
            break
    return chosen


def _late_receivables(forecast: ForecastResponse) -> list[CashSignal]:
    """Receivables due by the shortfall (or horizon) that are expected to arrive late."""
    cutoff = forecast.shortfall.day if forecast.shortfall else forecast.horizon_days
    late = [
        s
        for s in forecast.drivers
        if s.source_agent == "receivables"
        and s.kind == "inflow"
        and s.best_day <= cutoff
        and s.likely_day is not None
        and s.likely_day > s.best_day
    ]
    return sorted(late, key=lambda s: s.amount_myr * (s.likely_day - s.best_day), reverse=True)


def run_events(db, principal: AuthPrincipal, run_id: str) -> list[AgentRunEvent]:
    goal = goal_for(principal, run_id)
    route = plan(goal)
    steps: list[tuple[str, str, str, str | None]] = []

    def emit(kind: str, agent: str, message: str, action: str | None = None) -> None:
        steps.append((kind, agent, message, action))

    if route.empty:
        emit("run_started", "supervisor", "Goal received.")
        emit(
            "run_completed",
            "supervisor",
            "No built agent covers this goal. Agents can work on cash, collections or "
            "financing; ask FinBrain in the chat for anything else.",
        )
        return _events(run_id, steps)

    chosen = ["cashflow"]
    if route.cash or route.collections:
        chosen.append("receivables")
    if route.cash or route.financing:
        chosen.append("financing")
    emit("run_started", "supervisor", f"Goal received; routing to {', '.join(chosen)}.")

    authorize(db, principal, "cashflow", "forecast")
    today = dt.date.today()
    basis = cashflow.basis_for(db, principal, today)
    demo = basis.data_mode == DataMode.STUB

    def inbox_item(agent: str, title: str, summary: str, amount, source: str) -> str:
        if demo:
            return _INBOX[agent]
        reviewer = manifests.find_agent(agent).reviewer_job_function
        return review_inbox.propose(
            db,
            str(principal.tenant_id),
            agent_id=agent,
            reviewer=reviewer,
            title=title,
            summary=summary,
            amount=amount,
            evidence=[EvidenceRef(label=title, source=source)],
            draft=summary if agent == "receivables" else None,
        )

    forecast = cashflow_engine.build_forecast(basis, horizon_days=HORIZON_DAYS, as_of=today)
    shortfall = forecast.shortfall
    emit(
        "tool_called",
        "cashflow",
        f"forecast(horizon_days={HORIZON_DAYS}) → "
        + (f"shortfall on day {shortfall.day}" if shortfall else "no shortfall"),
    )
    if shortfall is not None:
        emit(
            "proposal_created",
            "cashflow",
            f"Shortfall on day {shortfall.day} ({shortfall.date:%d %b}): likely balance "
            f"{_ringgit(shortfall.likely_balance)} against a {_ringgit(shortfall.minimum_balance)} "
            f"minimum, a gap of {_ringgit(shortfall.gap)}.",
            inbox_item(
                "cashflow",
                f"Shortfall in {shortfall.day} days",
                f"Likely balance {_ringgit(shortfall.likely_balance)} against a "
                f"{_ringgit(shortfall.minimum_balance)} minimum on day {shortfall.day}.",
                shortfall.gap,
                "cashflow:forecast",
            ),
        )

    if "receivables" in chosen:
        authorize(db, principal, "receivables", "rank_overdue")
        late = _late_receivables(forecast)[:3]
        # Late invoices are paid on their due dates; failing that, the next receipts
        # are asked for before the shortfall day.
        if late:
            picked, ask = late, "collecting {it} on {its} due date{s}"
            shifts = [EventShift(event_id=s.id, shift_days=s.best_day - s.likely_day) for s in late]
        else:
            picked = _early_receivables(forecast)
            ask = f"asking for {{it}} before day {shortfall.day}" if shortfall else ""
            shifts = [
                EventShift(event_id=s.id, shift_days=shortfall.day - 1 - s.likely_day)
                for s in picked
            ]
        emit("tool_called", "receivables", f"rank_overdue(limit=3) → {len(picked)} found")
        if picked:
            invoices = ", ".join(_invoice_name(s.label) for s in sorted(picked, key=lambda s: s.id))
            one = len(picked) == 1
            ask = ask.format(
                it="it" if one else "them", its="its" if one else "their", s="" if one else "s"
            )
            total = sum((s.amount_myr for s in picked), Decimal("0"))
            scenario = cashflow_engine.build_forecast(
                basis, horizon_days=HORIZON_DAYS, as_of=forecast.as_of, shifts=shifts
            )
            if shortfall is None:
                effect = "keeps cash ahead of plan"
            elif scenario.shortfall is None or scenario.shortfall.day > shortfall.day:
                effect = "closes the gap"
            else:
                effect = f"narrows the gap to {_ringgit(scenario.shortfall.gap)}"
            message = (
                f"Reminder draft{'' if one else 's'} for {invoices} ({_ringgit(total)}): "
                f"{ask} {effect}."
            )
            emit(
                "proposal_created",
                "receivables",
                message,
                inbox_item(
                    "receivables",
                    f"Review {len(picked)} reminder draft{'' if one else 's'}",
                    message,
                    total,
                    "receivables:ranking",
                ),
            )

    if "financing" in chosen:
        authorize(db, principal, "financing", "match_products")
        gap = shortfall.gap if shortfall else Decimal("0.00")
        found = matches("MY", financing_profile.compute(db, str(principal.tenant_id), forecast))
        eligible = [m for m in found.matches if m.eligible]
        emit(
            "tool_called",
            "financing",
            f"match_products(gap={gap}) → {len(eligible)} of {len(found.matches)} eligible",
        )
        if eligible:
            best = eligible[0]
            emit(
                "proposal_created",
                "financing",
                f"{best.product.name} fits best ({best.fit_score}/100). {best.explanation} "
                "Application pack drafted.",
                # The demo company's sample inbox holds only the invoice-financing pack.
                None
                if demo and best.product.id != "my_invoice_financing"
                else inbox_item(
                    "financing",
                    f"Application pack: {best.product.name}",
                    f"{best.explanation} Covers the {_ringgit(gap)} gap.",
                    gap,
                    "financing:matches",
                ),
            )
        elif found.matches:
            # Nothing qualifies: say what stands between the company and the closest product.
            closest = min(
                found.matches,
                key=lambda m: (sum(not r.passed for r in m.rules), -m.fit_score),
            )
            missing = "; ".join(r.detail for r in closest.rules if not r.passed)
            emit(
                "proposal_created",
                "financing",
                f"Nothing qualifies yet. Closest: {closest.product.name}. Not met: {missing}.",
            )

    proposals = sum(1 for kind, *_ in steps if kind == "proposal_created")
    in_inbox = sum(1 for kind, *_, action in steps if kind == "proposal_created" and action)
    if in_inbox:
        emit(
            "waiting_for_review",
            "supervisor",
            f"{in_inbox} item{'s' if in_inbox != 1 else ''} await your review. "
            "Nothing is sent or paid until a person approves.",
        )
    if in_inbox or not proposals:
        done = "Run complete."
    else:
        done = (
            f"Run complete: {proposals} proposal{'s' if proposals != 1 else ''} above. "
            "Nothing has been sent or paid."
        )
    emit("run_completed", "supervisor", done)
    return _events(run_id, steps)


def _events(run_id: str, steps: list[tuple[str, str, str, str | None]]) -> list[AgentRunEvent]:
    return [
        AgentRunEvent(
            run_id=run_id,
            sequence=sequence,
            type=kind,
            agent_id=agent,
            message=message,
            action_id=action,
        )
        for sequence, (kind, agent, message, action) in enumerate(steps, start=1)
    ]
