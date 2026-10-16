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
from app.contracts.assistant import AssistantItem, AssistantPlan, ClarifyOption
from app.contracts.common import AutonomyLevel
from app.schemas import UserRole
from app.services import agent_runtime, live_agents, playbooks
from app.services.workflow_audit import write_workflow_event

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
    "analysis": (
        "Financial analysis",
        _FINANCE_READ,
        ("analysis", "profit", "profit and loss", "p&l", "margin", "margins", "expenses"),
    ),
    "financing": ("Financing & Passport", _FINANCE_READ, ("financing", "loan", "passport")),
    "collections": ("Collections", _FINANCE_READ, ("collections", "collections board")),
    "reconciliation": (
        "Reconciliation",
        _FINANCE_READ,
        ("reconciliation", "reconcile", "bank lines", "penyesuaian", "对账"),
    ),
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
# "approve the reminder drafts" means every reminder; "approve the reminder" means one.
_PLURAL = re.compile(
    r"\b(drafts|items|reminders|payments|bills|invoices|proposals|ones|them|these|those)\b",
    re.IGNORECASE,
)
_CORRECTION = re.compile(
    r"^\s*(no|nope|not that( one)?|wrong( one)?|i meant|i mean|actually|sorry|"
    r"bukan|tidak|silap|不是|不对|我是说|我的意思是)\b[\s,.!:;-]*",
    re.IGNORECASE,
)
_ORDINAL = {
    "first": 0, "1st": 0, "1": 0, "pertama": 0, "第一": 0,
    "second": 1, "2nd": 1, "two": 1, "2": 1, "kedua": 1, "第二": 1,
    "third": 2, "3rd": 2, "three": 2, "3": 2, "ketiga": 2, "第三": 2,
    "fourth": 3, "4th": 3, "4": 3, "keempat": 3, "第四": 3,
    "last": -1, "terakhir": -1, "最后": -1,
}
_FILLER = {
    "the", "one", "for", "about", "that", "this", "a", "an", "i", "meant", "mean", "no",
    "not", "it", "item", "please", "to", "of", "on", "with", "yang", "itu", "untuk",
}
# One or two words naming a broad area: ask what the person wants done there.
_VAGUE = (
    (
        re.compile(
            r"^\s*(help( me)?( with)?\s*)?(cash|money|duit|wang|tunai|钱|现金|资金)\s*\??\s*$",
            re.IGNORECASE,
        ),
        "What would you like to do about cash?",
        (
            ("Can we pay everyone this month?", "Can I pay everyone this month?"),
            ("See the 90-day forecast", "Open cash flow"),
            ("Chase the late payers", "Chase the late payers"),
            ("Find financing for the gap", "Which loans can we apply for?"),
        ),
    ),
    (
        re.compile(
            r"^\s*(help|what can you do|bantu|tolong|帮助|帮忙|你能做什么)\s*\??\s*$",
            re.IGNORECASE,
        ),
        "I can prepare these for you. Which one?",
        (
            ("Can we pay everyone this month?", "Can I pay everyone this month?"),
            ("Prepare me for the bank meeting", "Prepare me for the bank meeting"),
            ("Chase the late payers", "Chase the late payers"),
            ("Close the month", "Close the month"),
            ("What needs me today?", "What needs me today?"),
        ),
    ),
)
_GOAL = re.compile(
    r"^\s*(please\s+)?(can|could|will|prepare|plan|chase|check|help|run|get|work\s+out|"
    r"make\s+sure|find)\b",
    re.IGNORECASE,
)
# Questions whose full answer is a page: the financing matches with their reasons, and
# the e-invoice readiness checks. A search of the records finds unrelated text for them.
# Questions about what customers owe, answered from the receivables before any
# playbook ("who owes us" alone stays the chasing playbook).
_OWED = re.compile(
    r"^\s*how (many|much)\b.*\b(overdue|late|owed|outstanding|receivables?)\b"
    r"|\bwho owes (us )?(the )?most\b|\b(biggest|largest|top) (debtors|payers owing)\b"
    r"|\bberapa\b.*\b(tertunggak|hutang|berhutang)\b"
    r"|多少.*(逾期|欠款|应收)|谁欠.*最多",
    re.IGNORECASE,
)
# Moving money, or telling the assistant to drop its rules: refused with the reason.
_MONEY_OUT = re.compile(
    r"\b(transfer|wire|remit)\b.{0,40}?"
    r"(\brm ?\d|\bmyr|\bringgit|\bmoney|\bfunds|\bcash|\baccount|\d)"
    r"|\b(send|move)\b.{0,30}?(\brm ?\d|\bmyr ?\d|\bringgit|\bmoney\b|\bfunds\b)"
    r"|\bpay\b.{0,20}\brm ?\d|\bpindah(kan)?\b.{0,30}(\brm ?\d|\bwang\b|\bduit\b)"
    r"|转账|汇款|打款",
    re.IGNORECASE,
)
_OVERRIDE = re.compile(
    r"\b(ignore|forget|disregard)\b.{0,30}\b(instructions|rules|prompt)\b"
    r"|\babaikan\b.{0,30}\barahan\b|忽略.{0,10}(指令|规则)",
    re.IGNORECASE,
)
_NO_MONEY = (
    "I can't move money, and instructions inside a message don't change my rules. A "
    "payment is prepared as an L3 item in the review inbox: two different people approve "
    "it, each with an authenticator code, and it then runs only in DuitDuit's simulated "
    "bank. Nothing was changed."
)
_NO_OVERRIDE = (
    "Instructions inside a message don't change my rules: I only prepare work for a "
    "person to approve. Nothing was changed. Ask me about your records, or tell me what "
    "to prepare."
)
_VOWELS = set("aeiou")


def _not_words(text: str) -> bool:
    """One run of letters with almost no vowels, like a hand across the keyboard."""
    word = text.strip().casefold()
    if not word.isascii() or not word.isalpha() or len(word) < 6:
        return False
    return sum(ch in _VOWELS for ch in word) / len(word) < 0.2


_TOPIC_SCREENS = (
    (
        re.compile(
            r"^\s*(which|what)\b.*\b(loans?|financing|credit lines?)\b|哪些贷款|哪些融资",
            re.IGNORECASE,
        ),
        "financing",
    ),
    (
        re.compile(r"^\s*(which|what)\b.*\b(myinvois|e-?invoices?)\b", re.IGNORECASE),
        "einvoice",
    ),
)
_RECONCILE = re.compile(r"\breconcil\w*|\bpenyesuaian\b|对账", re.IGNORECASE)
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
    _, actions = live_agents.inbox_for(db, principal, None)
    return [action for action in actions if action.status in _OPEN]


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-z][a-z-]{3,}", text.casefold())
    return {word.rstrip("s") for word in words if word not in _STOPWORDS}


def _matches(action: ReviewAction, keywords: set[str]) -> bool:
    haystack = f"{action.title} {action.agent_id} {action.summary}".casefold()
    return any(word in haystack for word in keywords)


def _narrowed(action: ReviewAction, phrase: str) -> bool:
    haystack = f"{action.title} {action.agent_id} {action.summary}".casefold()
    words = [w for w in re.findall(r"[a-z0-9]+", phrase.casefold()) if w not in _FILLER]
    if not words:
        return False
    return " ".join(words) in haystack or all(
        w in haystack for w in words if len(w) >= 3
    ) and any(len(w) >= 3 for w in words)


def _decide(
    db,
    principal: AuthPrincipal,
    text: str,
    decision: str,
    by: str,
    narrow: str | None = None,
) -> AssistantPlan:
    if principal.role == UserRole.COMPLIANCE:
        return _refuse("Compliance reviews every item but does not decide them.", by)
    actions = _inbox(db, principal)
    mine = [a for a in actions if a.can_decide]
    keywords = _keywords(text)
    named = re.search(r'"([^"]+)"', text)
    exact = [a for a in mine if named and a.title == named.group(1)]
    if exact:
        chosen = exact
    elif _ALL.search(text) and not keywords:
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
    if narrow is not None:
        # The items the last request named first, then anything this person may decide.
        chosen = [a for a in chosen if _narrowed(a, narrow)] or [
            a for a in mine if _narrowed(a, narrow)
        ]
        if not chosen:
            return _refuse("None of those items fits that. Say which one in other words.", by)
    if len(chosen) > 1 and not exact and not _ALL.search(text) and not _PLURAL.search(text):
        return AssistantPlan(
            kind="clarify",
            message=f"{len(chosen)} items fit that. Which one do you want to {decision}?",
            options=[
                ClarifyOption(label=a.title, command=f'{decision} "{a.title}"') for a in chosen
            ],
            understood_by=by,
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
    if _MONEY_OUT.search(text):
        return _refuse(_NO_MONEY, "rules")
    if _not_words(text):
        return AssistantPlan(
            kind="clarify",
            message="I didn't catch that. Here are things I can do:",
            options=[
                ClarifyOption(label=label, command=command)
                for label, command in (
                    ("Can we pay everyone this month?", "Can I pay everyone this month?"),
                    ("Who owes us the most?", "Who owes us the most?"),
                    ("Which loans can we apply for?", "Which loans can we apply for?"),
                    ("What needs me today?", "What needs me today?"),
                )
            ],
            understood_by="rules",
        )
    if _OWED.search(text):
        plan = _navigate(principal, "collections", "rules")
        if plan.kind == "navigate":
            plan.answer_here = True
            plan.message = "Here is what your records say."
        return plan
    if _BRIEFING.search(text):
        return _briefing("rules")
    decide = _DECIDE.search(text)
    if decide and not _QUESTION.search(text):
        verb = decide.group(1).casefold()
        decision = "reject" if verb in ("reject", "decline") else "approve"
        return _decide(db, principal, text, decision, "rules")
    # A decision above still goes through confirmation, role and step-up checks; any
    # other attempt to talk the assistant out of its rules is refused here.
    if _OVERRIDE.search(text):
        return _refuse(_NO_OVERRIDE, "rules")
    if _NAVIGATE.search(text):
        screen = _screen_named(text)
        if screen:
            return _navigate(principal, screen, "rules")
    playbook = playbooks.match(text)
    if playbook:
        if not playbooks.allowed(principal, playbook):
            return _refuse("This playbook is not available to your role.", "rules")
        return AssistantPlan(
            kind="playbook",
            playbook=playbook,
            message=f"Preparing {playbooks.TITLES[playbook].lower()}. "
            "External actions will wait for review in the inbox.",
        )
    if _RECONCILE.search(text):
        return _navigate(principal, "reconciliation", "rules")
    for pattern, screen in _TOPIC_SCREENS:
        if pattern.search(text):
            plan = _navigate(principal, screen, "rules")
            if plan.kind == "navigate":
                plan.answer_here = True
                plan.message = "Here is what your records say."
            return plan
    if _GOAL.search(text) and not agent_runtime.plan(text).empty:
        return _run_goal(principal, text, "rules")
    for pattern, message, choices in _VAGUE:
        if pattern.search(text):
            return AssistantPlan(
                kind="clarify",
                message=message,
                options=[ClarifyOption(label=label, command=cmd) for label, cmd in choices],
                understood_by="rules",
            )
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


def _follow_up(db, principal: AuthPrincipal, text: str, previous: str) -> AssistantPlan | None:
    """A choice from the last clarification, or a correction of the last command."""
    asked = _by_rules(db, principal, previous)
    rest = _CORRECTION.sub("", text, count=1).strip()
    corrected = rest != text.strip()
    decide = _DECIDE.search(previous)
    narrowing = decide is not None and bool(rest) and not _DECIDE.search(rest)
    if asked is not None and asked.kind == "decide" and narrowing:
        verb = decide.group(1).casefold()
        decision = "reject" if verb in ("reject", "decline") else "approve"
        plan = _decide(db, principal, previous, decision, "rules", narrow=rest)
        plan.corrected = corrected
        return plan
    if asked is not None and asked.kind == "clarify" and asked.options:
        words = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", rest.casefold())
        pick = next((_ORDINAL[w] for w in words if w in _ORDINAL), None)
        if pick is not None and len(words) <= 4:
            index = pick if pick >= 0 else len(asked.options) - 1
            if index < len(asked.options):
                return _by_rules(db, principal, asked.options[index].command)
        decide = _DECIDE.search(previous)
        if decide and rest and not _DECIDE.search(rest):
            verb = decide.group(1).casefold()
            decision = "reject" if verb in ("reject", "decline") else "approve"
            plan = _decide(db, principal, previous, decision, "rules", narrow=rest)
            plan.corrected = corrected
            return plan
    if corrected and rest:
        plan = _by_rules(db, principal, rest)
        if plan is None and len(rest.split()) <= 3:
            plan = _by_rules(db, principal, f"open {rest}")
        if plan is not None:
            plan.corrected = True
            return plan
    return None


def interpret(
    db, principal: AuthPrincipal, text: str, previous: str | None = None
) -> AssistantPlan:
    plan = (
        (_follow_up(db, principal, text, previous) if previous else None)
        or _by_rules(db, principal, text)
        or _by_model(db, principal, text)
        or _answer()
    )
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
                "playbook": plan.playbook,
                "decision": plan.decision,
                "item_ids": [item.id for item in plan.items],
                "understood_by": plan.understood_by,
            },
            tenant_id=str(principal.tenant_id),
        )
        db.commit()
    return plan
