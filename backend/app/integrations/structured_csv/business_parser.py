"""Bounded deterministic CSV validation. No raw input in returned errors or logs."""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.contracts.customization import IMPORT_FIELDS, normalize_header
from app.contracts.imports import ImportIssue
from app.security.guardrails import content_risk

MAX_BYTES = 2_000_000
MAX_ROWS = 5000
MAX_CELL = 4096
MONEY_MAX = Decimal("999999999999.99")
STAGE_PROBABILITIES = {
    "quote": Decimal("0.30"),
    "order": Decimal("0.70"),
    "invoiced": Decimal("1.00"),
    # Received: kept for the financial analysis, never a future cash signal.
    "paid": Decimal("0.00"),
    "lost": Decimal("0.00"),
}
_NUMBER = re.compile(r"-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?")


class InvalidCell(ValueError):
    def __init__(self, field: str, code: str):
        self.field, self.code = field, code


@dataclass
class ParsedRow:
    number: int
    values: dict
    source_key: str


def read_csv(text: str) -> tuple[list[str], list[list[str]]]:
    if len(text.encode("utf-8")) > MAX_BYTES or "\x00" in text:
        raise InvalidCell("file", "invalid_file_size_or_encoding")
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        headers = next(reader)
        normalized = [normalize_header(h) for h in headers]
        if not 1 <= len(headers) <= 40 or any(not h or len(h) > 120 for h in normalized):
            raise InvalidCell("headers", "invalid_headers")
        if len(set(normalized)) != len(normalized):
            raise InvalidCell("headers", "duplicate_header")
        if any(ord(c) < 32 for h in headers for c in h):
            raise InvalidCell("headers", "control_character_in_header")
        rows = []
        for cells in reader:
            if not cells or all(not c.strip() for c in cells):
                continue
            if len(cells) != len(headers):
                raise InvalidCell("file", "row_width_mismatch")
            if any(len(c) > MAX_CELL for c in cells):
                raise InvalidCell("file", "cell_too_long")
            rows.append(cells)
            if len(rows) > MAX_ROWS:
                raise InvalidCell("file", "too_many_rows")
        if not rows:
            raise InvalidCell("file", "empty_csv")
        return headers, rows
    except (csv.Error, StopIteration) as error:
        raise InvalidCell("file", "invalid_csv") from error


def _text(row, field, default=None):
    value = row.get(field, "").strip()
    if not value:
        if default is not None:
            return default
        raise InvalidCell(field, "required")
    if len(value) > 240:
        raise InvalidCell(field, "text_too_long")
    if any(ord(c) < 32 for c in value):
        raise InvalidCell(field, "control_character")
    return value


def _money(row, field, default=None, *, signed=False, precision=2, maximum=MONEY_MAX):
    value = row.get(field, "").strip()
    if not value and default is not None:
        return Decimal(default)
    if not _NUMBER.fullmatch(value):
        raise InvalidCell(field, "invalid_decimal")
    try:
        number = Decimal(value.replace(",", ""))
    except InvalidOperation as error:
        raise InvalidCell(field, "invalid_decimal") from error
    if not number.is_finite() or abs(number) > maximum or (number < 0 and not signed):
        raise InvalidCell(field, "amount_out_of_range")
    if number != number.quantize(Decimal(1).scaleb(-precision)):
        raise InvalidCell(field, "too_many_decimal_places")
    return number.quantize(Decimal(1).scaleb(-precision))


def _day(row, field):
    value = _text(row, field)
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return date.fromisoformat(value)
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}", value):
            return datetime.strptime(value, "%d/%m/%Y").date()
    except ValueError:
        pass
    raise InvalidCell(field, "invalid_date")


def _integer(row, field, default="0"):
    value = _text(row, field, default)
    if not re.fullmatch(r"\d{1,9}", value):
        raise InvalidCell(field, "invalid_nonnegative_integer")
    return int(value)


def _enum(row, field, allowed, default):
    value = _text(row, field, default).casefold()
    if value not in allowed:
        raise InvalidCell(field, "invalid_option")
    return value


def _fx(row):
    currency = _text(row, "currency").upper()
    if currency not in {"MYR", "CNY", "USD", "SGD", "EUR", "GBP", "HKD"}:
        raise InvalidCell("currency", "unsupported_currency")
    rate = _money(
        row,
        "fx_rate",
        "1" if currency == "MYR" else None,
        precision=6,
        maximum=Decimal("999999.999999"),
    )
    if rate <= 0 or (currency == "MYR" and rate != 1):
        raise InvalidCell("fx_rate", "invalid_fx_rate")
    amount = _money(row, "amount")
    amount_myr = (amount * rate).quantize(Decimal("0.01"))
    if amount_myr > MONEY_MAX:
        raise InvalidCell("amount", "converted_amount_out_of_range")
    return {"currency": currency, "amount": amount, "fx_rate": rate, "amount_myr": amount_myr}


def validate_row(schema: str, row: dict) -> tuple[dict, str]:
    if schema == "bank_statement_v1":
        debit, credit = _money(row, "debit", "0"), _money(row, "credit", "0")
        if (debit > 0) == (credit > 0):
            raise InvalidCell("debit", "exactly_one_debit_or_credit_required")
        values = {
            "posted_on": _day(row, "date"),
            "description": _text(row, "description"),
            "direction": "out" if debit else "in",
            "amount": debit or credit,
            "balance": _money(row, "balance", signed=True) if row.get("balance") else None,
            "counterparty": row.get("counterparty", "").strip(),
        }
        # No reference in many bank exports: full normalized row is the identity fallback.
        key = row.get("reference", "").strip() or repr(
            sorted((k, str(v)) for k, v in values.items())
        )
    elif schema in {"payables_register_v1", "purchase_orders_v1"}:
        values = {**_fx(row), "supplier": _text(row, "supplier")}
        if schema == "payables_register_v1":
            values.update(
                bill_no=_text(row, "bill_id"),
                due_date=_day(row, "due_date"),
                status=_enum(row, "status", {"open", "paid", "cancelled"}, "open"),
                bank_account=row.get("bank_account", "").strip(),
            )
            key = values["supplier"].casefold() + ":" + values["bill_no"]
        else:
            values.update(
                po_no=_text(row, "po_no"),
                expected_delivery=_day(row, "expected_delivery"),
                expected_payment=_day(row, "expected_payment"),
                status=_enum(row, "status", {"open", "received", "paid", "cancelled"}, "open"),
            )
            key = values["supplier"].casefold() + ":" + values["po_no"]
    elif schema == "stock_v1":
        values = {
            "sku": _text(row, "sku"),
            "name": _text(row, "name"),
            "unit_cost": _money(row, "unit_cost"),
            "reorder_level": _integer(row, "reorder_level"),
            "lead_time_days": _integer(row, "lead_time_days", "30"),
            "on_hand": _integer(row, "on_hand"),
            "snapshot_date": _day(row, "snapshot_date"),
        }
        key = f"{values['sku']}:{values['snapshot_date']}"
    elif schema == "payroll_v1":
        period = _text(row, "period")
        if not re.fullmatch(r"\d{4}-(?:0[1-9]|1[0-2])", period) or period.startswith("0000"):
            raise InvalidCell("period", "invalid_period")
        values = {
            "period": period,
            "pay_date": _day(row, "pay_date"),
            "employee": _text(row, "employee"),
            "gross": _money(row, "gross"),
            "employer_contribution": _money(row, "employer_contribution"),
            "status": _enum(row, "status", {"draft", "approved", "paid"}, "draft"),
        }
        key = period + ":" + values["employee"].casefold()
    elif schema == "marketing_spend_v1":
        values = {
            "channel": _text(row, "channel"),
            "campaign_label": _text(row, "campaign"),
            "spend": _money(row, "spend"),
            "period_start": _day(row, "period_start"),
            "period_end": _day(row, "period_end"),
            "attributed_revenue": _money(row, "attributed_revenue")
            if row.get("attributed_revenue")
            else None,
        }
        if values["period_end"] < values["period_start"]:
            raise InvalidCell("period_end", "invalid_period_order")
        key = _text(row, "reference")
    elif schema == "marketplace_payouts_v1":
        values = {
            "platform": _text(row, "platform"),
            "payout_date": _day(row, "payout_date"),
            "gross": _money(row, "gross"),
            "fees": _money(row, "fees"),
            "net": _money(row, "net"),
            "status": _enum(row, "status", {"expected", "paid", "cancelled"}, "expected"),
        }
        if values["gross"] - values["fees"] != values["net"]:
            raise InvalidCell("net", "payout_does_not_reconcile")
        key = _text(row, "reference")
    else:
        stage = _enum(row, "stage", STAGE_PROBABILITIES, "quote")
        values = {
            "customer": _text(row, "customer"),
            "stage": stage,
            "amount": _money(row, "amount"),
            "expected_payment_date": _day(row, "expected_payment_date"),
            "probability": _money(
                row, "probability", str(STAGE_PROBABILITIES[stage]), maximum=Decimal(1)
            ),
        }
        if stage == "paid":
            values["probability"] = Decimal("0.00")
        key = _text(row, "reference")
    if len(key) > 1000:
        raise InvalidCell("reference", "reference_too_long")
    return values, key


def parse_rows(schema, headers, cells, column_map):
    targets = {normalize_header(k): v for k, v in column_map.items()}
    if not IMPORT_FIELDS[schema][1].issubset(targets.values()):
        raise InvalidCell("mapping", "incomplete_mapping")
    rows, issues = [], []
    for number, values in enumerate(cells, 2):
        risk = content_risk("\n".join(values))
        if risk:
            issues.append(ImportIssue(row=number, field="record", code=risk))
            continue
        mapped = {
            targets[normalize_header(h)]: v.strip()
            for h, v in zip(headers, values, strict=True)
            if normalize_header(h) in targets
        }
        try:
            parsed, key = validate_row(schema, mapped)
            rows.append(ParsedRow(number, parsed, key))
        except InvalidCell as error:
            issues.append(ImportIssue(row=number, field=error.field, code=error.code))
        if len(issues) >= 100:
            break
    return rows, issues
