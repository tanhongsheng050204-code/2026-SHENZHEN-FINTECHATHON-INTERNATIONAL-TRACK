"""Every product that is not yet eligible says the smallest next step, from the records."""

from decimal import Decimal

from app.contracts.common import DataMode
from app.stubs import financing


def _live(**values):
    return financing.Profile(DataMode.LIVE, {k: Decimal(v) for k, v in values.items()})


def _match(profile, product_id):
    return next(
        m for m in financing.matches("MY", profile).matches if m.product.id == product_id
    )


def test_invoice_financing_names_how_many_more_invoices_to_validate():
    profile = _live(
        validated_einvoice_share="0.16",
        einvoice_validated_count="3",
        einvoice_total_count="19",
        receivables_over_90_share="0",
    )

    match = _match(profile, "my_invoice_financing")

    assert (match.eligible, match.steps_away) == (False, 1)
    assert match.next_step == "Validate 7 more e-invoices (3 of 19 validated; 50% needed)."
    assert match.next_screen == "einvoice"


def test_a_missing_registration_date_points_to_company_settings():
    match = _match(_live(import_payables_share="0.52"), "my_trade_import")

    assert match.steps_away == 1
    assert match.next_step == "Declare your company registration date in Company settings."
    assert match.next_screen == "company"


def test_eligible_products_have_no_next_step_and_come_first():
    profile = _live(import_payables_share="0.52", months_trading="38")
    found = financing.matches("MY", profile).matches

    trade = next(m for m in found if m.product.id == "my_trade_import")
    assert (trade.eligible, trade.steps_away, trade.next_step) == (True, 0, None)
    # Ineligible products are ordered by how few steps they are from eligible.
    steps = [m.steps_away for m in found if not m.eligible]
    assert steps == sorted(steps)


def test_targets_out_of_reach_soon_say_so_plainly():
    match = _match(_live(months_trading="38", annual_revenue="2600000"), "my_term_loan")

    assert "RM3,000,000.00" in match.next_step and "now RM2,600,000.00" in match.next_step


def test_steps_nobody_can_take_in_the_app_have_no_link():
    match = _match(_live(months_trading="38", annual_revenue="2600000"), "my_term_loan")

    assert match.next_screen is None
