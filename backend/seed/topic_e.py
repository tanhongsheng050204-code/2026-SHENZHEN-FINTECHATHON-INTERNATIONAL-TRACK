"""Seed a dedicated synthetic tenant through the same mapped CSV import service.

No reset/deletes, provider calls, real identities, real bank accounts or MFA bypass
for HTTP routes. PostgreSQL requires migration/admin provisioning access.
"""

import argparse
import csv
import io
import json
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

from fastapi import HTTPException
from sqlalchemy import select

from app.auth.principal import AuthPrincipal
from app.contracts.customization import ImportMappingRequest
from app.db import SessionLocal, initialize_local_schema, set_worker_context
from app.models import (
    BankTransaction,
    BusinessImportBatch,
    Payable,
    PayrollRun,
    PurchaseOrder,
    SalesPipeline,
    SyntheticTenantSeed,
    Tenant,
    TenantSettingsRecord,
)
from app.schemas import UserRole
from app.security.keyring import ensure_active_key
from app.services.business_imports import commit_import
from app.services.import_mappings import save
from app.services.tenant_settings import initialize_settings

SEED_VERSION = 1
SEED_NAMESPACE = UUID("1ad693e6-f860-4c96-8054-b9b7a2e15410")
SEED_ACTOR = UUID("00000000-0000-0000-0000-000000000003")


def csv_text(headers, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue()


def datasets(as_of: date):
    def day(offset):
        return (as_of + timedelta(days=offset)).isoformat()

    def payroll_period(index):
        month_index = as_of.year * 12 + as_of.month - 1 + index
        return f"{month_index // 12:04}-{month_index % 12 + 1:02}"

    # 116,400 + 24,500 + 18,200 - 14,800 - 62,000 - (98,000 * .63) = 20,560.
    # Receipt dates are the likely dates already, not invoice due dates.
    bank_headers = ["Tarikh", "Tarikh Nilai", "Keterangan", "Debit", "Kredit", "Baki", "Rujukan"]
    bank_map = {
        "Tarikh": "date",
        "Keterangan": "description",
        "Debit": "debit",
        "Kredit": "credit",
        "Baki": "balance",
        "Rujukan": "reference",
    }
    data = {
        "bank_statement_v1": (
            bank_headers,
            bank_map,
            [
                [
                    day(0),
                    day(0),
                    "SYNTHETIC opening receipt",
                    "0.00",
                    "116400.00",
                    "116400.00",
                    "SYNTHETIC-BANK-OPEN",
                ]
            ],
        ),
        "payables_register_v1": (
            ["bill_id", "supplier", "amount", "currency", "fx_rate", "due_date", "status"],
            None,
            [
                [
                    "SYNTHETIC-RENT-1",
                    "SYNTHETIC local landlord",
                    "14800.00",
                    "MYR",
                    "1",
                    day(6),
                    "open",
                ],
                [
                    "SYNTHETIC-RENT-2",
                    "SYNTHETIC local landlord",
                    "14800.00",
                    "MYR",
                    "1",
                    day(36),
                    "open",
                ],
                [
                    "SYNTHETIC-LOGISTICS",
                    "SYNTHETIC local logistics",
                    "48300.00",
                    "MYR",
                    "1",
                    day(58),
                    "open",
                ],
                [
                    "SYNTHETIC-RENT-3",
                    "SYNTHETIC local landlord",
                    "14800.00",
                    "MYR",
                    "1",
                    day(66),
                    "open",
                ],
            ],
        ),
        "purchase_orders_v1": (
            [
                "po_no",
                "supplier",
                "amount",
                "currency",
                "fx_rate",
                "expected_delivery",
                "expected_payment",
                "status",
            ],
            None,
            [
                [
                    "SYNTHETIC-PO-1",
                    "SYNTHETIC Shenzhen Supplier 1",
                    "98000.00",
                    "CNY",
                    "0.630000",
                    day(28),
                    day(23),
                    "open",
                ],
                [
                    "SYNTHETIC-PO-2",
                    "SYNTHETIC Shenzhen Supplier 2",
                    "60000.00",
                    "CNY",
                    "0.630000",
                    day(80),
                    day(75),
                    "open",
                ],
            ],
        ),
        "stock_v1": (
            [
                "sku",
                "name",
                "unit_cost",
                "reorder_level",
                "lead_time_days",
                "on_hand",
                "snapshot_date",
            ],
            None,
            [
                [
                    "SYNTHETIC-HG-001",
                    "SYNTHETIC storage basket",
                    "18.00",
                    "120",
                    "30",
                    "85",
                    day(0),
                ],
                [
                    "SYNTHETIC-HG-002",
                    "SYNTHETIC kitchen organiser",
                    "32.00",
                    "90",
                    "35",
                    "62",
                    day(0),
                ],
                ["SYNTHETIC-HG-003", "SYNTHETIC desk lamp", "42.00", "60", "28", "44", day(0)],
            ],
        ),
        "payroll_v1": (
            ["period", "pay_date", "employee", "gross", "employer_contribution", "status"],
            None,
            [
                [
                    payroll_period(index),
                    day(offset),
                    f"SYNTHETIC Employee {i:02}",
                    "5000.00",
                    "1200.00",
                    "approved",
                ]
                for index, offset in enumerate((23, 53, 83))
                for i in range(1, 11)
            ],
        ),
        "marketing_spend_v1": (
            [
                "reference",
                "channel",
                "campaign",
                "spend",
                "period_start",
                "period_end",
                "attributed_revenue",
            ],
            None,
            [
                [
                    "SYNTHETIC-CAMP-1",
                    "SYNTHETIC marketplace ads",
                    "SYNTHETIC home goods promotion",
                    "5500.00",
                    day(40),
                    day(46),
                    "16500.00",
                ]
            ],
        ),
        "marketplace_payouts_v1": (
            ["reference", "platform", "payout_date", "gross", "fees", "net", "status"],
            None,
            [
                [
                    "SYNTHETIC-PAYOUT-1",
                    "SYNTHETIC Shopee settlement",
                    day(26),
                    "10000.00",
                    "600.00",
                    "9400.00",
                    "expected",
                ]
            ],
        ),
        "sales_pipeline_v1": (
            ["reference", "customer", "stage", "amount", "expected_payment_date", "probability"],
            None,
            [
                [
                    f"SYNTHETIC-INV-{i}",
                    f"SYNTHETIC Customer {customer}",
                    "invoiced",
                    amount,
                    day(offset),
                    "1.00",
                ]
                for i, (customer, amount, offset) in enumerate(
                    [
                        ("A", "24500.00", 11),
                        ("B", "18200.00", 21),
                        ("C", "31000.00", 30),
                        ("A", "42000.00", 38),
                        ("D", "38500.00", 43),
                        ("B", "27600.00", 54),
                        ("E", "44200.00", 61),
                        ("C", "35400.00", 70),
                        ("A", "52300.00", 80),
                        ("F", "39800.00", 87),
                    ],
                    1,
                )
            ]
            + [["SYNTHETIC-SO-311", "SYNTHETIC Customer G", "order", "26000.00", day(60), "0.70"]],
        ),
    }
    return {
        schema: (headers, mapping or {h: h for h in headers}, csv_text(headers, rows))
        for schema, (headers, mapping, rows) in data.items()
    }


def seed_basis(db, tenant_id: str, as_of: date):
    """A persisted-data reconciliation, not the Plan 4 forecast engine."""
    opening = db.scalar(
        select(BankTransaction)
        .where(BankTransaction.tenant_id == tenant_id, BankTransaction.posted_on <= as_of)
        .order_by(BankTransaction.posted_on.desc(), BankTransaction.id.desc())
        .limit(1)
    )
    if opening is None or opening.balance is None:
        raise RuntimeError("synthetic_opening_balance_missing")
    deltas = {}

    def add(day, amount):
        if day > as_of:
            deltas[day] = deltas.get(day, Decimal(0)) + amount

    for row in db.scalars(
        select(SalesPipeline).where(
            SalesPipeline.tenant_id == tenant_id, SalesPipeline.stage == "invoiced"
        )
    ):
        add(row.expected_payment_date, row.amount)
    for row in db.scalars(
        select(Payable).where(Payable.tenant_id == tenant_id, Payable.status == "open")
    ):
        add(row.due_date, -row.amount_myr)
    for row in db.scalars(
        select(PurchaseOrder).where(
            PurchaseOrder.tenant_id == tenant_id, PurchaseOrder.status == "open"
        )
    ):
        add(row.expected_payment, -row.amount_myr)
    for row in db.scalars(
        select(PayrollRun).where(PayrollRun.tenant_id == tenant_id, PayrollRun.status == "approved")
    ):
        add(row.pay_date, -row.total_gross - row.employer_contributions)
    settings = db.get(TenantSettingsRecord, tenant_id)
    minimum = Decimal(settings.document["alerts"]["minimum_cash_balance"])
    balance, first = opening.balance, None
    for day in sorted(deltas):
        balance += deltas[day]
        if balance < minimum:
            first = {
                "day": (day - as_of).days,
                "date": day.isoformat(),
                "balance_myr": str(balance),
                "minimum_myr": str(minimum),
                "gap_myr": str(minimum - balance),
            }
            break
    if first is None or first["day"] != 23 or Decimal(first["balance_myr"]) != Decimal("20560.00"):
        raise RuntimeError("synthetic_cash_basis_does_not_reconcile")
    return {
        "kind": "seed_reconciliation_not_forecast",
        "opening_balance_myr": str(opening.balance),
        "first_shortfall_basis": first,
        "drivers": ["payroll", "CNY supplier purchase order"],
        "invoice_dates": "Likely receipt dates; do not add collection delay a second time.",
    }


def main():
    parser = argparse.ArgumentParser(description="Non-destructive synthetic Topic E tenant seed")
    parser.add_argument("--as-of", type=date.fromisoformat, default=date(2026, 10, 9))
    parser.add_argument(
        "--export-dir", type=Path, help="Export clearly labelled synthetic CSVs and manifest"
    )
    parser.add_argument(
        "--allow-postgres", action="store_true", help="Use only a migrated, dedicated demo database"
    )
    args = parser.parse_args()
    tenant_id = str(uuid5(SEED_NAMESPACE, f"topic-e-v{SEED_VERSION}:{args.as_of}"))
    slug = f"synthetic-topic-e-v{SEED_VERSION}-{args.as_of}"
    principal = AuthPrincipal(
        user_id=SEED_ACTOR,
        email=None,
        role=UserRole.OWNER_DIRECTOR,
        tenant_id=UUID(tenant_id),
        job_functions=("owner",),
        aal="aal2",
    )
    initialize_local_schema()
    data = datasets(args.as_of)
    with SessionLocal() as db:
        if db.bind.dialect.name != "sqlite" and not args.allow_postgres:
            raise SystemExit(
                "PostgreSQL requires --allow-postgres and a dedicated migrated demo database."
            )
        tenant = db.get(Tenant, tenant_id)
        marker = db.get(SyntheticTenantSeed, tenant_id)
        if tenant and (marker is None or tenant.slug != slug):
            raise SystemExit("Refusing to seed an existing unmarked tenant.")
        if not tenant:
            tenant = Tenant(id=tenant_id, slug=slug, name="SYNTHETIC Malaysian Home Goods Importer")
            db.add(tenant)
            db.flush()
            initialize_settings(db, tenant_id, tenant.name)
            marker = SyntheticTenantSeed(
                tenant_id=tenant_id,
                version=SEED_VERSION,
                as_of=args.as_of,
                annual_revenue_myr=Decimal("2600000.00"),
                manifest={"synthetic": True, "seed_version": SEED_VERSION},
            )
            db.add(marker)
        # Provision the vault generation before entering the non-bypass worker role.
        ensure_active_key(db)
        db.flush()
        set_worker_context(db, tenant_id=tenant_id, actor_ref=f"synthetic-seed:{tenant_id}")
        results = []
        try:
            for schema, (headers, column_map, text) in data.items():
                mapping = save(
                    db,
                    principal,
                    ImportMappingRequest(
                        schema_name=schema,
                        name=f"SYNTHETIC {schema}"[:60],
                        headers=headers,
                        column_map=column_map,
                    ),
                    commit=False,
                )
                results.append(
                    commit_import(db, principal, schema, text, mapping.id, commit=False).model_dump(
                        mode="json"
                    )
                )
            basis = seed_basis(db, tenant_id, args.as_of)
            batch_count = len(
                db.scalars(
                    select(BusinessImportBatch).where(BusinessImportBatch.tenant_id == tenant_id)
                ).all()
            )
            db.commit()
        except (HTTPException, RuntimeError):
            db.rollback()
            raise
    manifest = {
        "synthetic": True,
        "tenant_id": tenant_id,
        "company": "SYNTHETIC Malaysian Home Goods Importer",
        "as_of": args.as_of.isoformat(),
        "annual_revenue_myr": "2600000.00",
        "seed_version": SEED_VERSION,
        "batch_count": batch_count,
        "imports": results,
        "cash_basis": basis,
        "access": (
            "No login/member created. Attach an existing authenticated user "
            "through controlled demo provisioning."
        ),
    }
    if args.export_dir:
        args.export_dir.mkdir(parents=True, exist_ok=True)
        for schema, (_, _, text) in data.items():
            (args.export_dir / f"SYNTHETIC-{schema}.csv").write_text(text, encoding="utf-8")
        (args.export_dir / "SYNTHETIC-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
