"""Stub financing catalogue and deterministic eligibility for the demo company.

Workstream B2 moves the catalogue into the jurisdiction packs and computes the
profile from real records. Categories are real; every term is illustrative.
"""

import datetime as dt
from dataclasses import dataclass
from decimal import Decimal

from app.contracts.agents import ReviewAction
from app.contracts.common import AutonomyLevel, DataMode, EvidenceRef, JobFunction
from app.contracts.financing import (
    FinancingMatch,
    FinancingMatchesResponse,
    FinancingProduct,
    Jurisdiction,
    PublicSignal,
    RuleResult,
    ScorecardResponse,
    ScoreFactor,
)

DISCLAIMER = (
    "Real product categories with illustrative terms. Not an offer of credit; "
    "confirm terms with the provider."
)
SHORTFALL_GAP = Decimal("29440.00")

_PROFILE: dict[str, Decimal] = {
    "months_trading": Decimal("38"),
    "annual_revenue": Decimal("2640000.00"),
    "validated_einvoice_share": Decimal("0.72"),
    "receivables_over_90_share": Decimal("0.08"),
    "top_customer_share": Decimal("0.31"),
    "import_payables_share": Decimal("0.46"),
    "anchor_buyer_programme": Decimal("0"),
    "projected_shortfall_gap": SHORTFALL_GAP,
}

_METRICS: dict[str, tuple[str, str, EvidenceRef]] = {
    "months_trading": (
        "Months trading",
        "months",
        EvidenceRef(label="Company registration date", source="profile:registration"),
    ),
    "annual_revenue": (
        "Annual revenue",
        "money",
        EvidenceRef(label="Validated e-invoices, last 12 months", source="einvoice:last-12-months"),
    ),
    "validated_einvoice_share": (
        "Validated e-invoice share",
        "share",
        EvidenceRef(label="Invoice validation status", source="einvoice:validation-status"),
    ),
    "receivables_over_90_share": (
        "Receivables over 90 days",
        "share",
        EvidenceRef(label="Receivables aging", source="finance:ar-aging"),
    ),
    "top_customer_share": (
        "Largest customer's share of revenue",
        "share",
        EvidenceRef(label="Revenue by customer", source="finance:top-customers"),
    ),
    "import_payables_share": (
        "Import payables share",
        "share",
        EvidenceRef(label="Supplier payables by currency", source="payables:currency-mix"),
    ),
    "anchor_buyer_programme": (
        "Anchor-buyer programme on record",
        "flag",
        EvidenceRef(label="Supply-chain programmes on record", source="profile:programmes"),
    ),
    "projected_shortfall_gap": (
        "Projected shortfall gap",
        "money",
        EvidenceRef(label="90-day forecast", source="cashflow:forecast"),
    ),
}


@dataclass(frozen=True)
class _Rule:
    rule: str
    metric: str
    op: str
    threshold: Decimal


@dataclass(frozen=True)
class _Product:
    product: FinancingProduct
    rules: tuple[_Rule, ...]
    fit_score: int


def _format(value: Decimal, unit: str) -> str:
    if unit == "money":
        return f"RM{value:,.2f}"
    if unit == "share":
        return f"{value * 100:.0f}%"
    return f"{value:.0f} months"


@dataclass(frozen=True)
class Profile:
    """The facts eligibility rules read. A missing fact fails its rule as not on record."""

    data_mode: DataMode
    values: dict[str, Decimal]


DEMO_PROFILE = Profile(DataMode.STUB, _PROFILE)


def _evaluate(rule: _Rule, profile: Profile = DEMO_PROFILE) -> RuleResult:
    label, unit, evidence = _METRICS[rule.metric]
    value = profile.values.get(rule.metric)
    if value is None:
        bound = "at least" if rule.op == ">=" else "at most"
        requirement = (
            "required" if unit == "flag" else f"requires {bound} " + _format(rule.threshold, unit)
        )
        return RuleResult(
            rule=rule.rule,
            passed=False,
            detail=f"{label}: not on record ({requirement})",
            evidence=[evidence],
        )
    passed = value >= rule.threshold if rule.op == ">=" else value <= rule.threshold
    if unit == "flag":
        detail = f"{label}: {'yes' if value else 'no'} (required)"
    else:
        bound = "at least" if rule.op == ">=" else "at most"
        detail = (
            f"{label}: {_format(value, unit)} (requires {bound} {_format(rule.threshold, unit)})"
        )
    return RuleResult(rule=rule.rule, passed=passed, detail=detail, evidence=[evidence])


def _product(
    product_id: str,
    jurisdiction: Jurisdiction,
    category: str,
    name: str,
    terms: str,
    rules: tuple[_Rule, ...],
    fit_score: int,
) -> _Product:
    return _Product(
        product=FinancingProduct(
            id=product_id,
            jurisdiction=jurisdiction,
            category=category,
            name=name,
            illustrative_terms=terms,
            last_verified=None,
            source_url=None,
        ),
        rules=rules,
        fit_score=fit_score,
    )


_MONTHS_24 = _Rule("months_trading_min", "months_trading", ">=", Decimal("24"))
_NO_ANCHOR = _Rule("anchor_programme_required", "anchor_buyer_programme", ">=", Decimal("1"))

_CATALOGUE: tuple[_Product, ...] = (
    _product(
        "my_invoice_financing",
        "MY",
        "invoice_financing",
        "Invoice financing",
        "Advance up to 80% of validated invoice value; repaid when the customer pays.",
        (
            _Rule("einvoice_share_min", "validated_einvoice_share", ">=", Decimal("0.50")),
            _Rule("aging_over_90_max", "receivables_over_90_share", "<=", Decimal("0.15")),
        ),
        92,
    ),
    _product(
        "my_trade_import",
        "MY",
        "trade_financing",
        "Import trade financing",
        "Pays overseas suppliers, including RMB settlement; repaid in 90 to 120 days.",
        (
            _Rule("import_share_min", "import_payables_share", ">=", Decimal("0.20")),
            _MONTHS_24,
        ),
        85,
    ),
    _product(
        "my_guarantee_scheme",
        "MY",
        "government_guarantee",
        "Government-guaranteed SME financing",
        "Bank financing with a partial government guarantee for viable SMEs.",
        (
            _Rule("months_trading_min", "months_trading", ">=", Decimal("12")),
            _Rule("revenue_max", "annual_revenue", "<=", Decimal("25000000.00")),
        ),
        78,
    ),
    _product(
        "my_islamic_working_capital",
        "MY",
        "islamic_working_capital",
        "Islamic working-capital financing (tawarruq)",
        "Shariah-compliant revolving working capital.",
        (_MONTHS_24, _Rule("revenue_min", "annual_revenue", ">=", Decimal("1000000.00"))),
        74,
    ),
    _product(
        "my_digital_micro",
        "MY",
        "digital_micro_financing",
        "Digital micro-financing",
        "Online application and fast decision, up to RM50,000.",
        (
            _Rule("months_trading_min", "months_trading", ">=", Decimal("6")),
            _Rule("gap_max", "projected_shortfall_gap", "<=", Decimal("50000.00")),
        ),
        66,
    ),
    _product(
        "my_term_loan",
        "MY",
        "working_capital_term_loan",
        "Working-capital term loan",
        "Three- to five-year term financing for working capital.",
        (_MONTHS_24, _Rule("revenue_min", "annual_revenue", ">=", Decimal("3000000.00"))),
        40,
    ),
    _product(
        "my_revolving_credit",
        "MY",
        "revolving_credit",
        "Revolving credit facility",
        "Draw and repay as needed within a limit.",
        (
            _Rule("months_trading_min", "months_trading", ">=", Decimal("36")),
            _Rule("revenue_min", "annual_revenue", ">=", Decimal("5000000.00")),
            _Rule("concentration_max", "top_customer_share", "<=", Decimal("0.40")),
        ),
        35,
    ),
    _product(
        "my_supply_chain",
        "MY",
        "supply_chain_financing",
        "Supply-chain financing",
        "Early payment through a large buyer's programme.",
        (_NO_ANCHOR,),
        30,
    ),
    _product(
        "cn_digital_sme_credit",
        "CN",
        "digital_sme_credit",
        "Digital SME credit line",
        "Online, data-driven unsecured credit line for small businesses.",
        (
            _MONTHS_24,
            _Rule("einvoice_share_min", "validated_einvoice_share", ">=", Decimal("0.50")),
        ),
        80,
    ),
    _product(
        "cn_invoice_financing",
        "CN",
        "invoice_financing",
        "Invoice financing",
        "Advance against validated tax invoices (fapiao).",
        (
            _Rule("einvoice_share_min", "validated_einvoice_share", ">=", Decimal("0.60")),
            _Rule("aging_over_90_max", "receivables_over_90_share", "<=", Decimal("0.10")),
        ),
        82,
    ),
    _product(
        "cn_inclusive_loan",
        "CN",
        "inclusive_finance_loan",
        "Inclusive-finance SME loan",
        "Policy-supported lending for small and micro enterprises.",
        (
            _Rule("months_trading_min", "months_trading", ">=", Decimal("12")),
            _Rule("revenue_max", "annual_revenue", "<=", Decimal("10000000.00")),
        ),
        70,
    ),
    _product(
        "cn_supply_chain",
        "CN",
        "supply_chain_financing",
        "Supply-chain financing",
        "Early payment through a core enterprise's programme.",
        (_NO_ANCHOR,),
        30,
    ),
)


def _match(entry: _Product, profile: Profile = DEMO_PROFILE) -> FinancingMatch:
    results = [_evaluate(rule, profile) for rule in entry.rules]
    failed = [result.detail for result in results if not result.passed]
    explanation = (
        f"Eligible: meets all {len(results)} requirements."
        if not failed
        else "Not eligible: " + "; ".join(failed) + "."
    )
    return FinancingMatch(
        product=entry.product,
        eligible=not failed,
        fit_score=entry.fit_score,
        rules=results,
        explanation=explanation,
    )


def matches(
    jurisdiction: Jurisdiction, profile: Profile = DEMO_PROFILE
) -> FinancingMatchesResponse:
    found = [
        _match(entry, profile) for entry in _CATALOGUE if entry.product.jurisdiction == jurisdiction
    ]
    found.sort(key=lambda match: (not match.eligible, -match.fit_score))
    return FinancingMatchesResponse(
        data_mode=profile.data_mode,
        jurisdiction=jurisdiction,
        disclaimer=DISCLAIMER,
        shortfall_gap=profile.values.get("projected_shortfall_gap"),
        matches=found,
    )


class PackError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def application_pack(product_id: str, profile: Profile = DEMO_PROFILE) -> ReviewAction:
    entry = next((e for e in _CATALOGUE if e.product.id == product_id), None)
    if entry is None:
        raise PackError("product_not_found", 404)
    match = _match(entry, profile)
    if not match.eligible:
        raise PackError("product_not_eligible", 409)
    return ReviewAction(
        id=f"act_pack_{product_id}",
        agent_id="financing",
        title=f"Application pack: {entry.product.name}",
        summary=match.explanation,
        autonomy_level=AutonomyLevel.L1,
        reviewer_job_function=JobFunction.OWNER,
        status="pending",
        amount=Decimal("60000.00"),
        draft=f"Requesting RM60,000.00 under {entry.product.name}. {match.explanation}",
        evidence=[evidence for result in match.rules for evidence in result.evidence],
        created_at=dt.datetime.now(dt.UTC),
    )


# ── Credit scorecard ─────────────────────────────────────────────────────────
# A points scorecard a lender can read line by line: each input falls in a
# published band, each band earns fixed points, and the total maps to a grade.
# The weights are set by hand (method "expert_weights"); fitting them on real
# repayment outcomes with logistic regression replaces them once that data exists.

SCORE_BASE = 300
SCORE_MAX = 800
SCORE_METHOD_NOTE = (
    "Points come from published bands set by hand, not from a model fitted on repayment "
    "outcomes. Calibrating the weights with logistic regression on real outcomes is planned."
)
PUBLIC_DATA_NOTE = (
    "Public signals come only from official platform APIs or exports the business owner "
    "provides; DuitDuit does not scrape. The signals shown here are synthetic demo data."
)

# (label, unit, evidence, max points, bands). A band is (lower bound, points):
# the first band whose lower bound the value reaches wins. For "lower is better"
# inputs the bands are upper bounds instead.
_BANDS: dict[str, tuple[str, str, EvidenceRef, int, str, tuple[tuple[Decimal, int], ...]]] = {
    "validated_einvoice_share": (
        "Validated e-invoice share",
        "share",
        EvidenceRef(label="Invoice validation status", source="einvoice:validation-status"),
        90,
        "higher",
        ((Decimal("0.70"), 90), (Decimal("0.50"), 60), (Decimal("0.30"), 30), (Decimal("0"), 0)),
    ),
    "receivables_over_90_share": (
        "Receivables over 90 days",
        "share",
        EvidenceRef(label="Receivables aging", source="finance:ar-aging"),
        80,
        "lower",
        ((Decimal("0.10"), 80), (Decimal("0.20"), 50), (Decimal("0.35"), 20), (Decimal("1"), 0)),
    ),
    "months_trading": (
        "Months trading",
        "months",
        EvidenceRef(label="Company registration date", source="profile:registration"),
        70,
        "higher",
        ((Decimal("48"), 70), (Decimal("24"), 50), (Decimal("12"), 25), (Decimal("0"), 0)),
    ),
    "top_customer_share": (
        "Largest customer's share of revenue",
        "share",
        EvidenceRef(label="Revenue by customer", source="finance:top-customers"),
        70,
        "lower",
        ((Decimal("0.20"), 70), (Decimal("0.35"), 45), (Decimal("0.50"), 20), (Decimal("1"), 0)),
    ),
    "bank_lines_matched_share": (
        "Bank lines matched to records",
        "share",
        EvidenceRef(label="Reconciliation", source="bank_statement:reconciliation"),
        60,
        "higher",
        ((Decimal("0.90"), 60), (Decimal("0.75"), 35), (Decimal("0"), 10)),
    ),
}

_SCORE_INPUTS: dict[str, Decimal] = {
    "validated_einvoice_share": _PROFILE["validated_einvoice_share"],
    "receivables_over_90_share": _PROFILE["receivables_over_90_share"],
    "months_trading": _PROFILE["months_trading"],
    "top_customer_share": _PROFILE["top_customer_share"],
    "bank_lines_matched_share": Decimal("0.94"),
}
_SHORTFALL_DAY = 23
_RATING_NOW = Decimal("4.4")
_RATING_90_DAYS_AGO = Decimal("4.5")

_PUBLIC_SIGNALS = (
    PublicSignal(
        source="google_maps",
        metric="Shop rating (212 reviews)",
        value="4.4 / 5",
        trend="4.5 → 4.4 over 90 days",
        status="ok",
        synthetic=True,
    ),
    PublicSignal(
        source="shopee",
        metric="Store rating (1,940 ratings)",
        value="4.8 / 5",
        trend="Steady; replies to 96% of chats",
        status="ok",
        synthetic=True,
    ),
)


def factor_points(key: str, value: Decimal) -> int:
    """Points for one input, from the published bands."""
    _label, _unit, _evidence, _max, direction, bands = _BANDS[key]
    for bound, points in bands:
        if (value >= bound) if direction == "higher" else (value <= bound):
            return points
    return 0


def runway_points(shortfall_day: int | None) -> int:
    """Fewer points the sooner cash falls below the minimum; None means no shortfall in 90 days."""
    if shortfall_day is None:
        return 80
    if shortfall_day > 60:
        return 60
    if shortfall_day > 30:
        return 40
    return 20


def reputation_points(rating_now: Decimal, rating_before: Decimal) -> int:
    """Public rating level and 90-day trend; a warning sign, never a cash movement."""
    drop = rating_before - rating_now
    if rating_now >= Decimal("4.2") and drop < Decimal("0.2"):
        return 50
    if rating_now >= Decimal("3.8") and drop <= Decimal("0.4"):
        return 30
    return 0


def grade_for(score: int) -> str:
    for floor, grade in ((720, "A"), (650, "B"), (580, "C"), (500, "D")):
        if score >= floor:
            return grade
    return "E"


def _band_factor(key: str, values: dict[str, Decimal] | None = None) -> ScoreFactor:
    label, unit, evidence, max_points, direction, bands = _BANDS[key]
    value = (_SCORE_INPUTS if values is None else values).get(key)
    if value is None:
        # No source in the tenant's records: no points, and no borrowed demo value.
        measured = key != "bank_lines_matched_share"
        return ScoreFactor(
            key=key,
            label=label,
            value="Not on record" if measured else "Not measured",
            points=0,
            max_points=max_points,
            reason="No source in your records yet, so this factor earns no points."
            if measured
            else "DuitDuit does not match bank lines to records yet, so this earns no points.",
            evidence=[evidence],
        )
    points = factor_points(key, value)
    bound = next(b for b, p in bands if p == points)
    if points == 0 and direction == "higher":
        floor = min(b for b, p in bands if p > 0)
        reason = f"Below {_format(floor, unit)} earns no points."
    elif direction == "higher":
        reason = f"At least {_format(bound, unit)} earns {points} of {max_points} points."
    else:
        reason = f"At most {_format(bound, unit)} earns {points} of {max_points} points."
    return ScoreFactor(
        key=key,
        label=label,
        value=_format(value, unit),
        points=points,
        max_points=max_points,
        reason=reason,
        evidence=[evidence],
    )


def scorecard(
    profile: Profile | None = None,
    *,
    shortfall_day: int | None = _SHORTFALL_DAY,
    public: bool = True,
) -> ScorecardResponse:
    """Score a profile. With no profile, the synthetic demo company is scored.

    A live profile is scored on exactly the facts its financing rules read, so the
    scorecard and the matches can never disagree. Bank-line matching is not measured
    yet; public signals are synthetic demo data and count only when `public` is set.
    """
    live = profile is not None and profile.data_mode == DataMode.LIVE
    values = profile.values if live else None
    factors = [
        _band_factor(key, values)
        for key in (
            "validated_einvoice_share",
            "receivables_over_90_share",
            "months_trading",
        )
    ]
    runway = runway_points(shortfall_day)
    factors.append(
        ScoreFactor(
            key="cash_runway",
            label="Cash runway",
            value=f"Shortfall on day {shortfall_day}"
            if shortfall_day is not None
            else "No shortfall in 90 days",
            points=runway,
            max_points=80,
            reason="Cash falls below the minimum within 30 days."
            if shortfall_day is not None and shortfall_day <= 30
            else "The earlier cash falls below the minimum, the fewer points.",
            evidence=[EvidenceRef(label="90-day forecast", source="cashflow:forecast")],
        )
    )
    factors += [
        _band_factor(key, values) for key in ("top_customer_share", "bank_lines_matched_share")
    ]
    if public:
        reputation = reputation_points(_RATING_NOW, _RATING_90_DAYS_AGO)
        factors.append(
            ScoreFactor(
                key="public_reputation",
                label="Public reputation",
                value=f"Rating {_RATING_NOW} (was {_RATING_90_DAYS_AGO} 90 days ago)",
                points=reputation,
                max_points=50,
                reason="A rating of 4.2 or more that fell by less than 0.2 earns full points.",
                evidence=[
                    EvidenceRef(label="Public ratings (synthetic demo)", source="public:ratings")
                ],
            )
        )
    else:
        factors.append(
            ScoreFactor(
                key="public_reputation",
                label="Public reputation",
                value="Not connected",
                points=0,
                max_points=50,
                reason="No platform ratings are connected, so this factor earns no points.",
                evidence=[EvidenceRef(label="Public ratings", source="public:ratings")],
            )
        )
    score = SCORE_BASE + sum(f.points for f in factors)
    return ScorecardResponse(
        data_mode=DataMode.LIVE if live else DataMode.STUB,
        method="expert_weights",
        method_note=SCORE_METHOD_NOTE,
        score=score,
        min_score=SCORE_BASE,
        max_score=SCORE_MAX,
        grade=grade_for(score),
        base_points=SCORE_BASE,
        factors=factors,
        public_signals=list(_PUBLIC_SIGNALS) if public else [],
        public_data_note=PUBLIC_DATA_NOTE,
        disclaimer=DISCLAIMER,
    )
