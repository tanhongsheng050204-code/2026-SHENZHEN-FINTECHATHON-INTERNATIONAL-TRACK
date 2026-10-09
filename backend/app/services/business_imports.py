"""Plan 3 import transaction. Typed facts stay in SQL; model-facing values are bands.

No provider/model calls, raw CSV storage, automatic account verification or cash
signals. Plan 4/5 consume these facts and must avoid counting POs/bills twice.
"""

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.principal import AuthPrincipal
from app.config import get_settings
from app.contracts.customization import IMPORT_FIELDS, header_fingerprint, normalize_header
from app.contracts.imports import CsvImportPreview, CsvImportResult, ImportIssue
from app.integrations.structured_csv.business_parser import (
    MONEY_MAX,
    InvalidCell,
    ParsedRow,
    parse_rows,
    read_csv,
)
from app.models import (
    BankTransaction,
    BusinessImportBatch,
    Customer,
    InventoryItem,
    MarketingSpend,
    MarketplacePayout,
    Payable,
    PayrollLine,
    PayrollRun,
    PurchaseOrder,
    SalesPipeline,
    StockSnapshot,
    Supplier,
    SupplierBankChange,
    SyntheticTenantSeed,
    TokenizedContent,
)
from app.schemas import UserRole
from app.security.guardrails import record_event
from app.security.tokenize import amount_band_index, protect_scalar
from app.services import import_mappings
from app.services.identity import audit, tenant_lock

MODELS = {
    "bank_statement_v1": BankTransaction,
    "payables_register_v1": Payable,
    "purchase_orders_v1": PurchaseOrder,
    "stock_v1": StockSnapshot,
    "payroll_v1": PayrollLine,
    "marketing_spend_v1": MarketingSpend,
    "marketplace_payouts_v1": MarketplacePayout,
    "sales_pipeline_v1": SalesPipeline,
}
WRITER_JOBS = {
    "bank_statement_v1": ("finance",),
    "payables_register_v1": ("finance",),
    "purchase_orders_v1": ("procurement", "logistics"),
    "stock_v1": ("procurement", "logistics"),
    "payroll_v1": ("hr",),
    "marketing_spend_v1": ("marketing",),
    "marketplace_payouts_v1": ("marketing",),
    "sales_pipeline_v1": ("sales", "customer_service"),
}


def authorize(principal: AuthPrincipal, schema: str):
    if principal.role == UserRole.OWNER_DIRECTOR:
        return
    if schema in {"bank_statement_v1", "payables_register_v1"}:
        allowed = principal.role == UserRole.FINANCE_OPS
    else:
        allowed = bool(set(principal.job_functions).intersection(WRITER_JOBS[schema]))
    if principal.role == UserRole.COMPLIANCE or not allowed:
        raise HTTPException(403, "import_job_function_required")


def digest(tenant_id: str, namespace: str, value: str) -> str:
    return hmac.new(
        get_settings().token_identity_secret.encode(),
        f"{tenant_id}:{namespace}:{value}".encode(),
        hashlib.sha256,
    ).hexdigest()


def row_identity(tenant_id: str, schema: str, row: ParsedRow) -> tuple[str, str]:
    canonical = json.dumps(row.values, sort_keys=True, default=str, separators=(",", ":"))
    return (
        f"csv3:{schema}:{digest(tenant_id, schema, row.source_key)}",
        digest(tenant_id, "record", canonical),
    )


@dataclass
class PreparedImport:
    preview: CsvImportPreview
    rows: list[ParsedRow]
    batch_id: str


def _existing_issues(db, tenant_id, schema, rows):
    issues, accepted, seen, duplicates = [], [], {}, 0
    model = MODELS[schema]
    stock_seen, payroll_groups = {}, {}
    for row in rows:
        source_id, record_hash = row_identity(tenant_id, schema, row)
        if source_id in seen:
            if seen[source_id] != record_hash:
                issues.append(
                    ImportIssue(row=row.number, field="reference", code="conflicting_duplicate")
                )
            else:
                duplicates += 1
            continue
        seen[source_id] = record_hash
        existing = db.scalar(
            select(model).where(model.tenant_id == tenant_id, model.source_record_id == source_id)
        )
        if existing:
            if existing.record_hash != record_hash:
                issues.append(
                    ImportIssue(row=row.number, field="reference", code="immutable_record_conflict")
                )
            else:
                duplicates += 1
            continue
        value = row.values
        if schema == "stock_v1":
            definition = {
                k: value[k] for k in ("name", "unit_cost", "reorder_level", "lead_time_days")
            }
            item = db.scalar(
                select(InventoryItem).where(
                    InventoryItem.tenant_id == tenant_id,
                    InventoryItem.sku == digest(tenant_id, "sku", value["sku"]),
                )
            )
            if item:
                token = _derive_text(tenant_id, value["name"])
                valid = item.name == token and all(
                    getattr(item, k) == definition[k]
                    for k in ("unit_cost", "reorder_level", "lead_time_days")
                )
            else:
                valid = value["sku"] not in stock_seen or stock_seen[value["sku"]] == definition
            stock_seen[value["sku"]] = definition
            if not valid:
                issues.append(
                    ImportIssue(row=row.number, field="sku", code="inventory_definition_conflict")
                )
        if schema == "payroll_v1":
            period = value["period"]
            run = db.scalar(
                select(PayrollRun).where(
                    PayrollRun.tenant_id == tenant_id, PayrollRun.period == period
                )
            )
            if run:
                issues.append(
                    ImportIssue(row=row.number, field="period", code="payroll_run_already_sealed")
                )
            previous = payroll_groups.setdefault(
                period,
                {
                    "pay_date": value["pay_date"],
                    "status": value["status"],
                    "gross": Decimal(0),
                    "contribution": Decimal(0),
                },
            )
            if previous["pay_date"] != value["pay_date"] or previous["status"] != value["status"]:
                issues.append(
                    ImportIssue(row=row.number, field="period", code="inconsistent_payroll_run")
                )
            previous["gross"] += value["gross"]
            previous["contribution"] += value["employer_contribution"]
            if (
                previous["gross"] > MONEY_MAX
                or previous["contribution"] > MONEY_MAX
                or previous["gross"] + previous["contribution"] > MONEY_MAX
            ):
                issues.append(
                    ImportIssue(row=row.number, field="gross", code="payroll_total_out_of_range")
                )
        accepted.append(row)
    return accepted, duplicates, issues[:100]


def _derive_text(tenant_id, value):
    from app.security.tokenize import derive_token

    return derive_token("TEXT", value, tenant_id)


def prepare(db: Session, principal: AuthPrincipal, schema: str, csv_text: str, mapping_id=None):
    authorize(principal, schema)
    tenant_id = str(principal.tenant_id)
    try:
        headers, cells = read_csv(csv_text)
        mapping = import_mappings.match(db, tenant_id, schema, headers, mapping_id)
        if mapping_id and mapping is None:
            raise InvalidCell("mapping", "mapping_not_found_or_headers_changed")
        if mapping:
            column_map = mapping.column_map
        else:
            column_map = {
                h: normalize_header(h)
                for h in headers
                if normalize_header(h) in IMPORT_FIELDS[schema][0]
            }
            if not IMPORT_FIELDS[schema][1].issubset(column_map.values()):
                raise InvalidCell("mapping", "mapping_required")
        rows, issues = parse_rows(schema, headers, cells, column_map)
        accepted, duplicates, conflicts = _existing_issues(db, tenant_id, schema, rows)
        issues = (issues + conflicts)[:100]
        fingerprint = header_fingerprint(headers)
        mapping_ref = mapping.id if mapping else None
        batch_id = "imp_" + digest(
            tenant_id,
            schema + ":batch",
            csv_text
            + json.dumps({normalize_header(k): v for k, v in column_map.items()}, sort_keys=True),
        )
        preview = CsvImportPreview(
            schema_name=schema,
            mapping_id=mapping_ref,
            fingerprint=fingerprint,
            total_rows=len(cells),
            accepted_rows=len(accepted),
            duplicate_rows=duplicates,
            issues=issues,
            can_commit=not issues,
        )
        return PreparedImport(preview, accepted, batch_id)
    except InvalidCell as error:
        return PreparedImport(
            CsvImportPreview(
                schema_name=schema,
                mapping_id=mapping_id,
                fingerprint="",
                total_rows=0,
                accepted_rows=0,
                duplicate_rows=0,
                issues=[ImportIssue(row=0, field=error.field, code=error.code)],
                can_commit=False,
            ),
            [],
            "",
        )


def _protect(db, tenant_id, source_id, value, kind="TEXT", employee=False):
    return protect_scalar(
        db,
        entity_type=kind,
        value=value,
        source_record_id=source_id,
        tenant_id=tenant_id,
        data_class="employee_personal" if employee else "customer_personal",
    )


def _supplier(db, tenant_id, source_id, values):
    identity = digest(tenant_id, "supplier", normalize_header(values["supplier"]))
    row = db.scalar(
        select(Supplier).where(
            Supplier.tenant_id == tenant_id, Supplier.normalized_name == identity
        )
    )
    if not row:
        row = Supplier(
            tenant_id=tenant_id,
            normalized_name=identity,
            name_token=_protect(db, tenant_id, source_id, values["supplier"], "ORG"),
            currency=values["currency"],
        )
        db.add(row)
        db.flush()
    account = values.get("bank_account")
    if account:
        token = _protect(db, tenant_id, source_id, account, "BANKACC")
        # Every unverified account from an import is a proposal, never a verified destination.
        if token != row.verified_bank_account_token:
            db.add(
                SupplierBankChange(
                    tenant_id=tenant_id,
                    supplier_id=row.id,
                    proposed_account_token=token,
                    source_record_id=source_id,
                    status="quarantined",
                )
            )
            record_event(
                db,
                tenant_id,
                "ASI06",
                "Supplier bank account quarantined",
                "Imported bank details require callback verification and a separate review.",
                "quarantined",
            )
    return row.id


def _persist_row(db, tenant_id, schema, batch_id, row, payroll_runs):
    values = dict(row.values)
    source_id, record_hash = row_identity(tenant_id, schema, row)
    common = {
        "tenant_id": tenant_id,
        "batch_id": batch_id,
        "source_record_id": source_id,
        "record_hash": record_hash,
    }
    if schema == "bank_statement_v1":
        description = values.pop("description")
        counterparty = values.pop("counterparty")
        fact = BankTransaction(
            **common,
            **values,
            description_token=_protect(db, tenant_id, source_id, description),
            counterparty_token=_protect(db, tenant_id, source_id, counterparty, "ORG")
            if counterparty
            else None,
        )
    elif schema in {"payables_register_v1", "purchase_orders_v1"}:
        supplier_id = _supplier(db, tenant_id, source_id, values)
        values.pop("supplier")
        values.pop("bank_account", None)
        ref = "bill_no" if schema == "payables_register_v1" else "po_no"
        values[ref] = _protect(db, tenant_id, source_id, values[ref])
        fact = MODELS[schema](**common, **values, supplier_id=supplier_id)
    elif schema == "stock_v1":
        identity = digest(tenant_id, "sku", values["sku"])
        item = db.scalar(
            select(InventoryItem).where(
                InventoryItem.tenant_id == tenant_id, InventoryItem.sku == identity
            )
        )
        if not item:
            item = InventoryItem(
                tenant_id=tenant_id,
                sku=identity,
                name=_protect(db, tenant_id, source_id, values["name"]),
                **{k: values[k] for k in ("unit_cost", "reorder_level", "lead_time_days")},
            )
            db.add(item)
            db.flush()
        fact = StockSnapshot(
            **common,
            item_id=item.id,
            on_hand=values["on_hand"],
            snapshot_date=values["snapshot_date"],
        )
    elif schema == "payroll_v1":
        run = payroll_runs[values["period"]]
        fact = PayrollLine(
            **common,
            run_id=run.id,
            employee_token=_protect(db, tenant_id, source_id, values["employee"], "PERSON", True),
            gross_amount_token=_protect(
                db, tenant_id, source_id, f"RM {values['gross']:.2f}", "AMOUNT", True
            ),
            gross_band=f"AMOUNT_BAND_{amount_band_index(values['gross'])}",
        )
        # No per-employee contribution in SQL/search. Only aggregated contributions.
    elif schema == "marketing_spend_v1":
        values["channel"] = _protect(db, tenant_id, source_id, values["channel"])
        values["campaign_label"] = _protect(db, tenant_id, source_id, values["campaign_label"])
        fact = MarketingSpend(**common, **values)
    elif schema == "marketplace_payouts_v1":
        values["platform"] = _protect(db, tenant_id, source_id, values["platform"])
        fact = MarketplacePayout(**common, **values)
    else:
        customer = values.pop("customer")
        identity = digest(tenant_id, "customer", normalize_header(customer))
        token = _protect(db, tenant_id, source_id, customer, "ORG")
        customer_row = db.scalar(
            select(Customer).where(
                Customer.tenant_id == tenant_id, Customer.normalized_name == identity
            )
        )
        if not customer_row:
            customer_row = Customer(
                tenant_id=tenant_id,
                normalized_name=identity,
                canonical_name=token,
                primary_name_token=token,
                profile_origin="manual",
            )
            db.add(customer_row)
            db.flush()
        fact = SalesPipeline(**common, **values, customer_token=token, customer_id=customer_row.id)
    db.add(fact)
    db.flush()
    _model_record(db, tenant_id, schema, fact, source_id)


def _model_record(db, tenant_id, schema, fact, source_id):
    safe = {"schema": schema, "source_ref": f"{fact.__tablename__}:{fact.id}"}
    # Payroll search contains only period-level bands, never employee identifiers/tokens.
    if schema == "payroll_v1":
        return
    for column in fact.__table__.columns:
        key = column.name
        value = getattr(fact, key)
        if (
            key in {"id", "tenant_id", "batch_id", "source_record_id", "record_hash"}
            or value is None
        ):
            continue
        if isinstance(value, Decimal):
            safe[key + "_band"] = (
                f"AMOUNT_BAND_{amount_band_index(value)}" if key != "probability" else str(value)
            )
        elif isinstance(value, date):
            safe[key] = value.isoformat()
        else:
            safe[key] = value
    synthetic = db.get(SyntheticTenantSeed, tenant_id) is not None
    safe["synthetic"] = synthetic
    content = json.dumps(safe, sort_keys=True)
    db.add(
        TokenizedContent(
            tenant_id=tenant_id,
            source_record_id=source_id,
            source_system="business_csv",
            record_type=schema,
            content_text=content,
            content_fingerprint=digest(tenant_id, "model-record", content),
            safe_metadata=safe,
            processing_status="protected",
            enrichment_mode="deterministic_import",
        )
    )


def commit_import(
    db: Session,
    principal: AuthPrincipal,
    schema: str,
    csv_text: str,
    mapping_id=None,
    *,
    commit=True,
):
    tenant_id = str(principal.tenant_id)
    tenant_lock(db, tenant_id)
    prepared = prepare(db, principal, schema, csv_text, mapping_id)
    if not prepared.preview.can_commit:
        if any(
            i.code in {"prompt_injection", "supplier_bank_change"} for i in prepared.preview.issues
        ):
            record_event(
                db,
                tenant_id,
                "ASI01",
                "CSV import blocked",
                "Untrusted instructions detected; no financial facts were persisted.",
                "blocked",
            )
            if commit:
                db.commit()
        raise HTTPException(
            422,
            {
                "code": "import_validation_failed",
                "issues": [i.model_dump() for i in prepared.preview.issues],
            },
        )
    existing = db.scalar(
        select(BusinessImportBatch).where(
            BusinessImportBatch.tenant_id == tenant_id, BusinessImportBatch.id == prepared.batch_id
        )
    )
    if existing:
        return CsvImportResult(
            schema_name=schema,
            batch_id=existing.id,
            imported_rows=0,
            duplicate_rows=existing.imported_rows + existing.duplicate_rows,
            replayed=True,
            synthetic=existing.synthetic,
        )
    synthetic = db.get(SyntheticTenantSeed, tenant_id) is not None
    batch = BusinessImportBatch(
        id=prepared.batch_id,
        tenant_id=tenant_id,
        schema_name=schema,
        mapping_id=prepared.preview.mapping_id,
        fingerprint=prepared.preview.fingerprint,
        imported_rows=len(prepared.rows),
        duplicate_rows=prepared.preview.duplicate_rows,
        created_by=str(principal.user_id),
        synthetic=synthetic,
    )
    try:
        db.add(batch)
        db.flush()
        payroll_runs = {}
        if schema == "payroll_v1":
            for row in prepared.rows:
                value = row.values
                period = value["period"]
                if period not in payroll_runs:
                    run = PayrollRun(
                        tenant_id=tenant_id,
                        batch_id=batch.id,
                        period=period,
                        pay_date=value["pay_date"],
                        status=value["status"],
                        total_gross=Decimal(0),
                        employer_contributions=Decimal(0),
                    )
                    payroll_runs[period] = run
                    db.add(run)
                payroll_runs[period].total_gross += value["gross"]
                payroll_runs[period].employer_contributions += value["employer_contribution"]
            db.flush()
        for row in prepared.rows:
            _persist_row(db, tenant_id, schema, batch.id, row, payroll_runs)
        audit(
            db,
            principal,
            "import.committed",
            "business_import_batch",
            batch.id,
            schema=schema,
            imported_rows=batch.imported_rows,
            duplicate_rows=batch.duplicate_rows,
            synthetic=synthetic,
        )
        if commit:
            db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "import_conflict_refresh_preview") from error
    return CsvImportResult(
        schema_name=schema,
        batch_id=batch.id,
        imported_rows=batch.imported_rows,
        duplicate_rows=batch.duplicate_rows,
        replayed=False,
        synthetic=synthetic,
    )
