"""Malaysian financing products follow public schemes and quote only what their source states."""

import datetime as dt
import re

from app.stubs import financing

CHECKED = dt.date(2026, 10, 11)
# Every figure a product's terms may quote, as its public source states it.
STATED = {
    "my_invoice_financing": set(),
    "my_trade_import": set(),
    "my_guarantee_scheme": {"1%"},
    "my_islamic_working_capital": set(),
    "my_digital_micro": {"RM50,000"},
    "my_term_loan": {"RM5 million", "5 years", "7%", "30 June 2021"},
}
UNSOURCED = {"my_revolving_credit", "my_supply_chain"}
FIGURE = re.compile(
    r"RM\d[\d,.]*\d(?: million)?|RM\d(?: million)?|\d+(?:\.\d+)?%"
    r"|\d+ (?:years|months|days)|\d{1,2} \w+ \d{4}"
)


def _products():
    return {entry.product.id: entry.product for entry in financing._CATALOGUE}


def test_each_malaysian_product_names_a_public_source_and_when_it_was_checked():
    products = _products()
    for product_id in STATED:
        product = products[product_id]
        assert product.source_url and product.source_url.startswith("https://"), product_id
        assert product.last_verified == CHECKED, product_id
        assert product.illustrative_terms.startswith("Modelled on "), product_id


def test_terms_quote_no_figure_their_source_does_not_state():
    products = _products()
    for product_id, allowed in STATED.items():
        figures = set(FIGURE.findall(products[product_id].illustrative_terms))
        assert figures <= allowed, (product_id, figures - allowed)


def test_products_without_a_checked_source_claim_none():
    products = _products()
    for product_id in UNSOURCED | {p for p in products if p.startswith("cn_")}:
        assert products[product_id].source_url is None, product_id
        assert products[product_id].last_verified is None, product_id
        assert not products[product_id].illustrative_terms.startswith("Modelled on "), product_id
