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
    RuleResult,
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


def _evaluate(rule: _Rule) -> RuleResult:
    label, unit, evidence = _METRICS[rule.metric]
    value = _PROFILE[rule.metric]
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


def _match(entry: _Product) -> FinancingMatch:
    results = [_evaluate(rule) for rule in entry.rules]
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


def matches(jurisdiction: Jurisdiction) -> FinancingMatchesResponse:
    found = [_match(entry) for entry in _CATALOGUE if entry.product.jurisdiction == jurisdiction]
    found.sort(key=lambda match: (not match.eligible, -match.fit_score))
    return FinancingMatchesResponse(
        data_mode=DataMode.STUB,
        jurisdiction=jurisdiction,
        disclaimer=DISCLAIMER,
        shortfall_gap=SHORTFALL_GAP,
        matches=found,
    )


class PackError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def application_pack(product_id: str) -> ReviewAction:
    entry = next((e for e in _CATALOGUE if e.product.id == product_id), None)
    if entry is None:
        raise PackError("product_not_found", 404)
    match = _match(entry)
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
