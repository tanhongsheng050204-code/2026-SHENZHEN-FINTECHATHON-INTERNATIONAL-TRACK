"""The remaining position-workspace skills, each computed from records already kept.

live_agents computes the forecast-based skills; these read the review inbox, the
collections holds, the financial analysis, stock, e-invoices, protected messages,
Passports and the guardrail log. Each says plainly when its records are missing,
and none writes anything: opening a workspace never adds an audit event.
"""

import datetime as dt
from collections.abc import Callable
from decimal import Decimal

from sqlalchemy import func, select

from app.auth.principal import AuthPrincipal
from app.contracts.cashflow import ForecastResponse
from app.contracts.common import EvidenceRef
from app.contracts.positions import SkillResult
from app.models import (
    AuthUserRole,
    EInvoiceRecord,
    InventoryItem,
    PurchaseOrder,
    SecurityGuardrailEvent,
    StockSnapshot,
    SupplierBankChange,
    TokenizedContent,
)

_OPEN = ("pending", "awaiting_second_approval", "edited")
_STALE = dt.timedelta(hours=48)


def _result(skill_id, title, value, summary, status, source) -> SkillResult:
    return SkillResult(
        skill_id=skill_id,
        title=title,
        value=value,
        summary=summary,
        status=status,
        evidence=[EvidenceRef(label=title, source=source)],
    )


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _aware(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


def compute(
    db, principal: AuthPrincipal, forecast: ForecastResponse, money: Callable[[Decimal], str]
) -> dict[str, SkillResult]:
    from app.services import collections, financial_analysis, passports, review_inbox

    tenant_id = str(principal.tenant_id)
    results: dict[str, SkillResult] = {}
    _, actions = review_inbox.inbox(db, principal, None)
    open_items = [a for a in actions if a.status in _OPEN]

    def waiting(agent_id: str) -> list:
        return [a for a in open_items if a.agent_id == agent_id]

    results["scenarios"] = _result(
        "scenarios",
        "What-if scenarios",
        "Ready",
        "Move any payment earlier or later on Cash & finance, What if, and see whether the "
        "gap closes. Your books never change.",
        "ok",
        "cashflow:what-if",
    )
    packs = waiting("financing")
    results["application_pack"] = _result(
        "application_pack",
        "Application packs",
        _plural(len(packs), "pack") + " waiting" if packs else "None waiting",
        "Drafted from your records and waiting for the owner in the review inbox."
        if packs
        else "Prepare one from a financing match; it waits for the owner before anything goes.",
        "attention" if packs else "ok",
        "financing:packs",
    )
    issued = passports.list_for(db, tenant_id)
    latest = max(issued, key=lambda p: p.version) if issued else None
    results["readiness_passport"] = _result(
        "readiness_passport",
        "Financing Readiness Passport",
        f"Version {latest.version}" if latest else "Not issued",
        f"Issued {latest.issued_at:%d %b %Y}, hashed and anchored on your audit chain."
        if latest
        else "Issue one on Financing & Passport to share with a lender.",
        "ok" if latest else "attention",
        "financing:passport",
    )

    ratios = {r.key: r for r in financial_analysis.analyse(db, tenant_id, forecast.as_of).ratios}
    get_paid, pay_out = ratios.get("days_to_get_paid"), ratios.get("days_to_pay_suppliers")
    if get_paid and pay_out and get_paid.value is not None and pay_out.value is not None:
        gap = get_paid.value - pay_out.value
        results["cash_conversion_cycle"] = _result(
            "cash_conversion_cycle",
            "Cash conversion gap",
            f"{gap:.1f} days",
            f"Days to get paid ({get_paid.value:.1f}) minus days to pay suppliers "
            f"({pay_out.value:.1f}). Days of stock are not included.",
            "attention" if gap > 0 else "ok",
            "analysis:ratios",
        )
    else:
        results["cash_conversion_cycle"] = _result(
            "cash_conversion_cycle",
            "Cash conversion gap",
            None,
            "Not measured: it needs sales received and supplier bills on record.",
            "ok",
            "analysis:ratios",
        )
    marketing = ratios.get("marketing_return")
    results["return_per_ringgit"] = _result(
        "return_per_ringgit",
        "Return per ringgit",
        f"RM{marketing.value:.2f}" if marketing and marketing.value is not None else None,
        "Attributed revenue divided by marketing spend, campaigns ending in the last 3 months."
        if marketing and marketing.value is not None
        else "Not measured: it needs marketing spend with attributed revenue.",
        "ok",
        "marketing:spend",
    )

    now = dt.datetime.now(dt.UTC)
    stale = [a for a in open_items if now - _aware(a.created_at) > _STALE]
    results["stale_approvals"] = _result(
        "stale_approvals",
        "Approvals waiting over 48 hours",
        str(len(stale)),
        ", ".join(a.title for a in stale[:3]) if stale else "Nothing has waited over 48 hours.",
        "attention" if stale else "ok",
        "inbox:ages",
    )
    reminders = waiting("receivables")
    results["draft_reminders"] = _result(
        "draft_reminders",
        "Reminder drafts",
        _plural(len(reminders), "draft"),
        "Waiting for approval in the review inbox; nothing is sent before that."
        if reminders
        else "No reminder draft is waiting.",
        "attention" if reminders else "ok",
        "receivables:reminders",
    )
    holds = collections.holds(db, principal, forecast.as_of)
    promised = [h for h in holds if h.kind == "promised"]
    disputed = [h for h in holds if h.kind == "disputed"]
    results["payment_promises"] = _result(
        "payment_promises",
        "Promises to pay",
        str(len(promised)),
        "; ".join(f"{h.label} by {h.until:%d %b}" for h in promised[:3] if h.until)
        or "No promise to pay is on record.",
        "ok",
        "collections:holds",
    )

    quarantined = db.scalar(
        select(func.count())
        .select_from(SupplierBankChange)
        .where(
            SupplierBankChange.tenant_id == tenant_id,
            SupplierBankChange.status == "quarantined",
        )
    ) or 0
    bank_items = [a for a in waiting("payables") if "bank" in a.title.casefold()]
    flagged = quarantined + len(bank_items)
    results["bank_change_check"] = _result(
        "bank_change_check",
        "Supplier bank changes held",
        str(flagged),
        f"{_plural(quarantined, 'imported change')} quarantined and "
        f"{_plural(len(bank_items), 'review item')} open. A change needs callback "
        "verification and two different approvers."
        if flagged
        else "No unverified supplier bank details.",
        "risk" if flagged else "ok",
        "payables:bank-changes",
    )

    board = collections.board(db, principal, forecast.as_of)
    overdue = {
        c.customer_label
        for column in board.columns
        for c in column.cards
        if c.days_overdue > 0 and c.hold is None
    }
    results["credit_check"] = _result(
        "credit_check",
        "Customers to check before a new order",
        str(len(overdue)),
        "Overdue now: " + ", ".join(sorted(overdue)[:3]) + "."
        if overdue
        else "No customer has an overdue invoice.",
        "attention" if overdue else "ok",
        "collections:board",
    )

    messages = db.scalars(
        select(TokenizedContent.structured_summary).where(
            TokenizedContent.tenant_id == tenant_id,
            TokenizedContent.source_system.in_(("email", "telegram")),
        )
    ).all()
    needing = sum(1 for s in messages if s and s.get("action_required"))
    results["triage_messages"] = _result(
        "triage_messages",
        "Messages needing action",
        f"{needing} of {len(messages)}",
        "Protected email and Telegram records whose summary asks for action."
        if messages
        else "No email or Telegram records yet.",
        "attention" if needing else "ok",
        "sources:messages",
    )
    replies = waiting("customer_service")
    results["suggest_replies"] = _result(
        "suggest_replies",
        "Reply drafts",
        _plural(len(replies), "draft"),
        "Waiting for review; a person sends each one." if replies else "No reply draft waiting.",
        "attention" if replies else "ok",
        "customer_service:replies",
    )
    results["dispute_risk"] = _result(
        "dispute_risk",
        "Disputes",
        str(len(disputed)),
        "Invoices marked disputed are not chased until resolved: "
        + ", ".join(h.label for h in disputed[:3])
        + "."
        if disputed
        else "No invoice is marked disputed.",
        "attention" if disputed else "ok",
        "collections:holds",
    )

    orders = db.execute(
        select(PurchaseOrder.supplier_id, func.sum(PurchaseOrder.amount_myr)).where(
            PurchaseOrder.tenant_id == tenant_id
        ).group_by(PurchaseOrder.supplier_id)
    ).all()
    total = sum((amount or Decimal(0) for _, amount in orders), Decimal(0))
    top = max((amount or Decimal(0) for _, amount in orders), default=Decimal(0))
    results["supplier_comparison"] = _result(
        "supplier_comparison",
        "Supplier spread",
        _plural(len(orders), "supplier") if orders else None,
        f"Largest supplier takes {top / total * 100:.0f}% of {money(total)} in purchase orders."
        if total
        else "No purchase orders on record.",
        "attention" if total and top / total > Decimal("0.6") else "ok",
        "purchasing:orders",
    )

    latest_day = (
        select(StockSnapshot.item_id, func.max(StockSnapshot.snapshot_date).label("day"))
        .where(StockSnapshot.tenant_id == tenant_id, StockSnapshot.snapshot_date <= forecast.as_of)
        .group_by(StockSnapshot.item_id)
        .subquery()
    )
    stock = db.execute(
        select(StockSnapshot.on_hand, InventoryItem.reorder_level, InventoryItem.unit_cost)
        .join(
            latest_day,
            (latest_day.c.item_id == StockSnapshot.item_id)
            & (latest_day.c.day == StockSnapshot.snapshot_date),
        )
        .join(
            InventoryItem,
            (InventoryItem.id == StockSnapshot.item_id) & (InventoryItem.tenant_id == tenant_id),
        )
        .where(StockSnapshot.tenant_id == tenant_id)
    ).all()
    below = sum(1 for on_hand, reorder, _ in stock if on_hand < reorder)
    results["reorder_alerts"] = _result(
        "reorder_alerts",
        "Below reorder level",
        _plural(below, "SKU") if stock else None,
        f"Out of {_plural(len(stock), 'SKU')} in the latest stock count."
        if stock
        else "No stock count on record.",
        "attention" if below else "ok",
        "inventory:stock",
    )
    tied_up = sum((Decimal(on_hand) * cost for on_hand, _, cost in stock), Decimal(0))
    results["cash_in_stock"] = _result(
        "cash_in_stock",
        "Cash tied up in stock",
        money(tied_up) if stock else None,
        "Units on hand times unit cost, latest stock count."
        if stock
        else "No stock count on record.",
        "ok",
        "inventory:stock",
    )

    invoices = db.execute(
        select(EInvoiceRecord.status, EInvoiceRecord.supplier_tin).where(
            EInvoiceRecord.tenant_id == tenant_id
        )
    ).all()
    to_fix = sum(1 for status, tin in invoices if not tin or status == "review")
    validated = sum(1 for status, _ in invoices if status == "validated")
    results["einvoice_readiness"] = _result(
        "einvoice_readiness",
        "e-Invoices to fix",
        str(to_fix) if invoices else None,
        f"{validated} of {_plural(len(invoices), 'e-invoice')} validated; "
        f"{to_fix} missing a supplier TIN or waiting for review."
        if invoices
        else "No e-invoices on record.",
        "attention" if to_fix else "ok",
        "einvoice:records",
    )
    since = now - dt.timedelta(days=30)
    blocked = db.scalar(
        select(func.count())
        .select_from(SecurityGuardrailEvent)
        .where(
            SecurityGuardrailEvent.tenant_id == tenant_id,
            SecurityGuardrailEvent.occurred_at >= since,
        )
    ) or 0
    results["ai_oversight"] = _result(
        "ai_oversight",
        "Guardrail events, 30 days",
        str(blocked),
        "Blocked or quarantined requests; each is listed on Trust & audit."
        if blocked
        else "Nothing blocked in the last 30 days.",
        "attention" if blocked else "ok",
        "trust:guardrails",
    )
    members = db.scalars(
        select(AuthUserRole).where(
            AuthUserRole.tenant_id == tenant_id, AuthUserRole.active.is_(True)
        )
    ).all()
    month = dt.timedelta(days=30)
    idle = [
        m for m in members if m.last_active_at is None or now - _aware(m.last_active_at) > month
    ]
    results["access_review"] = _result(
        "access_review",
        "Accounts to review",
        str(len(idle)),
        f"{_plural(len(idle), 'active account')} never signed in or idle over 30 days."
        if idle
        else "Every active account was used in the last 30 days.",
        "attention" if idle else "ok",
        "team:access",
    )
    return results
