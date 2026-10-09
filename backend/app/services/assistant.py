"""DuitDuit's front door: turn what a person types or says into one allowed action.

The assistant never acts on its own. It returns a plan the person sees first:
open a page, hand a goal to the agents, decide review-inbox items (only after the
person confirms, and only items their role may decide), show the briefing, or pass
the words on as a question. Everything else is refused with the reason.

Understanding is rules first (repeatable, offline). Words the rules cannot place
may go to the model, which can only pick from the same allowed actions; its pick
passes through the same role checks, and any failure falls back to answering the
words as a question. Text that still contains personal data never reaches the model.

Each command is recorded on the tenant's audit chain by kind and target ids,
never by its words.
"""

import json
import re
import secrets

from app.auth.principal import AuthPrincipal
from app.config import get_settings
from app.contracts.agents import ReviewAction
from app.contracts.assistant import AssistantItem, AssistantPlan
from app.contracts.common import AutonomyLevel
from app.schemas import UserRole
from app.services import agent_runtime, job_scope, live_agents, review_inbox
from app.services.workflow_audit import write_workflow_event
from app.stubs import inbox as stub_inbox

_EVERYONE = tuple(UserRole)
_FINANCE_READ = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)
_FINANCE_WORK = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR)
_OVERSIGHT = (UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)
_RUN_ROLES = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR)

# Screen id -> (label, roles that may open it, words that name it). Mirrors
# frontend/src/lib/access.ts; the backend's own route checks stay the authority.
SCREENS: dict[str, tuple[str, tuple[UserRole, ...], tuple[str, ...]]] = {
    "home": ("Today", _EVERYONE, ("today", "home", "dashboard")),
    "agents": ("Ask DuitDuit", _EVERYONE, ("ask", "chat", "assistant")),
    "inbox": ("Review inbox", _EVERYONE, ("inbox", "review", "approvals", "proposals")),
    "positions": ("Positions", _EVERYONE, ("position", "positions", "workspace")),
    "autonomy": ("Agents & autonomy", _EVERYONE, ("agents", "autonomy", "kill switch")),
    "customers": ("Customers", _EVERYONE, ("customer", "customers", "debtors")),
    "settings": ("My preferences", _EVERYONE, ("preferences", "my settings", "profile")),
    "cashflow": ("Cash & finance", _FINANCE_READ, ("cash", "cash flow", "cashflow", "forecast")),
    "finance": ("Receivables & intelligence", _FINANCE_READ, ("receivables", "revenue")),
    "financing": ("Financing & Passport", _FINANCE_READ, ("financing", "loan", "passport")),
    "einvoice": (
        "e-Invoicing",
        _FINANCE_READ,
        ("e-invoicing", "einvoicing", "e-invoice", "einvoice", "invoices", "invoice"),
    ),
    "company": ("Company settings", _FINANCE_READ, ("company settings", "company")),
    "ingestion": ("Data sources", _FINANCE_WORK, ("data sources", "import", "upload")),
    "team": ("Team", _OVERSIGHT, ("team", "staff", "members")),
    "trust": ("Trust & audit", _OVERSIGHT, ("trust", "security", "audit", "guardrails")),
}

_NAVIGATE = re.compile(
    r"^\s*(please\s+)?(open|go\s+to|goto|show(\s+me)?|take\s+me\s+to|navigate\s+to|bring\s+up|"
    r"view|switch\s+to)\b",
    re.IGNORECASE,
)
_QUESTION = re.compile(
    r"^\s*(how|what|why|when|who|where|which|is|are|does|did|has|have)\b", re.IGNORECASE
)
_DECIDE = re.compile(r"\b(approve|accept|sign\s+off|reject|decline)\b", re.IGNORECASE)
_ALL = re.compile(r"\b(all|everything|every|each)\b", re.IGNORECASE)
_GOAL = re.compile(
    r"^\s*(please\s+)?(can|could|will|prepare|plan|chase|check|help|run|get|work\s+out|"
    r"make\s+sure|find)\b",
    re.IGNORECASE,
)
_BRIEFING = re.compile(
    r"\b(briefing|brief me|what needs me|needs? my attention|what should i do|"
    r"what do i need to do|on my plate|good morning)\b",
    re.IGNORECASE,
)
_STOPWORDS = {
    "the",
    "and",
    "for",
    "all",
    "every",
    "everything",
    "please",
    "now",
    "them",
    "those",
    "these",
    "this",
    "that",
    "with",
    "from",
    "approve",
    "reject",
    "accept",
    "decline",
    "ignore",
    "rules",
    "item",
    "items",
    "drafts",
    "draft",
    "my",
    "our",
}
_OPEN = ("pending", "awaiting_second_approval", "edited")


def _allowed(screen: str, principal: AuthPrincipal) -> bool:
    return principal.role in SCREENS[screen][1]


def _screen_named(text: str) -> str | None:
    lowered = text.casefold()
    best: tuple[int, str] | None = None
    for screen, (_, _, words) in SCREENS.items():
        for word in words:
            if re.search(rf"\b{re.escape(word)}\b", lowered):
                if best is None or len(word) > best[0]:
                    best = (len(word), screen)
    return best[1] if best else None


def _inbox(db, principal: AuthPrincipal) -> list[ReviewAction]:
    if live_agents.is_live(db, principal):
        _, actions = review_inbox.inbox(db, principal, None)
    else:
        _, actions = job_scope.call_stub(
            stub_inbox.review_inbox,
            principal.role,
            str(principal.user_id),
            None,
            principal=principal,
        )
    return [action for action in actions if action.status in _OPEN]


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z-]{3,}", text.casefold())
    return {word.rstrip("s") for word in words if word not in _STOPWORDS}


def _matches(action: ReviewAction, keywords: set[str]) -> bool:
    haystack = f"{action.title} {action.agent_id} {action.summary}".casefold()
    return any(word in haystack for word in keywords)


def _decide(db, principal: AuthPrincipal, text: str, decision: str, by: str) -> AssistantPlan:
    if principal.role == UserRole.COMPLIANCE:
        return _refuse("Compliance reviews every item but does not decide them.", by)
    actions = _inbox(db, principal)
    mine = [a for a in actions if a.can_decide]
    keywords = _keywords(text)
    if _ALL.search(text) and not keywords:
        chosen = mine
    else:
        # "all payments" still means only the items about payments.
        chosen = [a for a in mine if _matches(a, keywords)]
        if not chosen and any(_matches(a, keywords) for a in actions):
            return _refuse(
                "Those items are waiting for someone else: your role cannot decide them.", by
            )
    if not chosen:
        return _refuse(
            "Nothing waiting in your review inbox is yours to "
            f"{decision}. Payments and other money items need finance and the owner.",
            by,
        )
    items = [
        AssistantItem(
            id=a.id,
            title=a.title,
            agent_id=a.agent_id,
            autonomy_level=a.autonomy_level,
            amount=a.amount,
        )
        for a in chosen
    ]
    count = len(items)
    return AssistantPlan(
        kind="decide",
        decision=decision,
        items=items,
        needs_confirmation=True,
        needs_step_up=any(i.autonomy_level == AutonomyLevel.L3 for i in items),
        message=f"I'll {decision} {count} item{'s' if count != 1 else ''} once you confirm.",
        understood_by=by,
    )


def _navigate(principal: AuthPrincipal, screen: str, by: str) -> AssistantPlan:
    label = SCREENS[screen][0]
    if not _allowed(screen, principal):
        return _refuse(f"{label} is not available to your role.", by)
    return AssistantPlan(
        kind="navigate", screen=screen, message=f"Opening {label}.", understood_by=by
    )


def _run_goal(principal: AuthPrincipal, text: str, by: str) -> AssistantPlan:
    if principal.role not in _RUN_ROLES:
        return _refuse("Only finance and the owner can hand goals to the agents.", by)
    return AssistantPlan(
        kind="run_goal",
        goal=text.strip(),
        message="Handing this to the agents. Their proposals go to your review inbox.",
        understood_by=by,
    )


def _refuse(message: str, by: str) -> AssistantPlan:
    return AssistantPlan(kind="refuse", message=message, understood_by=by)


def _answer(by: str = "rules") -> AssistantPlan:
    return AssistantPlan(
        kind="answer", message="Looking that up in your records.", understood_by=by
    )


def _briefing(by: str) -> AssistantPlan:
    return AssistantPlan(kind="briefing", message="Here is what needs you today.", understood_by=by)


def _by_rules(db, principal: AuthPrincipal, text: str) -> AssistantPlan | None:
    if _BRIEFING.search(text):
        return _briefing("rules")
    decide = _DECIDE.search(text)
    if decide and not _QUESTION.search(text):
        verb = decide.group(1).casefold()
        decision = "reject" if verb in ("reject", "decline") else "approve"
        return _decide(db, principal, text, decision, "rules")
    if _NAVIGATE.search(text):
        screen = _screen_named(text)
        if screen:
            return _navigate(principal, screen, "rules")
    if _GOAL.search(text) and not agent_runtime.plan(text).empty:
        return _run_goal(principal, text, "rules")
    return None


def _model_interpret(text: str) -> dict | None:
    """Ask the model to pick one allowed action. None when unavailable or unsafe."""
    settings = get_settings()
    if not settings.gemini_api_key:
        return None
    from app.security.detect import contains_known_pii
    from app.services.gemini import gemini_client

    if contains_known_pii(text):
        return None
    instruction = (
        "You map a finance app user's request to exactly one allowed action. Reply with "
        'JSON only: {"kind": one of navigate|run_goal|decide|briefing|answer, '
        '"screen": one of ' + "|".join(SCREENS) + " (navigate only), "
        '"decision": approve|reject (decide only), "target": short words naming the '
        'items (decide only)}. Use "answer" for questions about records. Never invent '
        "other kinds or screens."
    )
    response = gemini_client().models.generate_content(
        model=settings.gemini_reasoning_model,
        contents=text,
        config={"system_instruction": instruction, "response_mime_type": "application/json"},
    )
    return json.loads(response.text or "null")


def _by_model(db, principal: AuthPrincipal, text: str) -> AssistantPlan | None:
    try:
        picked = _model_interpret(text)
    except Exception:
        # Provider down, slow or unparsable: the words are answered as a question.
        return None
    if not isinstance(picked, dict):
        return None
    kind = picked.get("kind")
    if kind == "navigate" and picked.get("screen") in SCREENS:
        return _navigate(principal, picked["screen"], "model")
    if kind == "decide" and picked.get("decision") in ("approve", "reject"):
        target = str(picked.get("target") or "")
        return _decide(db, principal, f"{target} {text}", picked["decision"], "model")
    if kind == "run_goal":
        return _run_goal(principal, text, "model")
    if kind == "briefing":
        return _briefing("model")
    return None


def interpret(db, principal: AuthPrincipal, text: str) -> AssistantPlan:
    plan = _by_rules(db, principal, text) or _by_model(db, principal, text) or _answer()
    if db is not None:
        write_workflow_event(
            db,
            event_type="assistant_command",
            actor_role=principal.role.value,
            actor_ref=str(principal.user_id),
            resource_type="assistant",
            resource_id="cmd_" + secrets.token_hex(6),
            event_payload={
                "kind": plan.kind,
                "screen": plan.screen,
                "decision": plan.decision,
                "item_ids": [item.id for item in plan.items],
                "understood_by": plan.understood_by,
            },
            tenant_id=str(principal.tenant_id),
        )
        db.commit()
    return plan
