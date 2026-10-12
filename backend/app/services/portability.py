"""PDPA data portability: one customer's records as a machine-readable document.

Compliance only, after a recent authenticator check. Protected values are opened
through privacy.export_token, so each one is a role-gated disclosure on the
disclosure audit chain, exactly like a single PDPA access request; a value the
role may not see stays masked. The export itself is recorded on the workflow chain
as "data_export_prepared" with the subject's kind, id and the sections included.
"""

import datetime as dt

from sqlalchemy import select

from app.auth.principal import AuthPrincipal
from app.models import Customer, CustomerEndpoint, EInvoiceRecord, SalesPipeline
from app.security.detokenize import hash_query
from app.services.privacy import export_token
from app.services.workflow_audit import write_workflow_event

FORMAT = "duitduit-portability-v1"
SECTIONS = ["identity", "contacts", "receivables", "einvoices"]


def _opened(db, principal: AuthPrincipal, token: str | None) -> dict | None:
    if not token:
        return None
    try:
        found = export_token(
            db,
            token,
            str(principal.tenant_id),
            role=principal.role,
            query_hash=hash_query(f"portability-export:{token}"),
            actor_ref=principal.actor_ref,
        )
    except LookupError:
        return None
    return {
        "kind": found.entity_type,
        "value": found.decrypted_value if found.decrypted_value is not None else found.masked_value,
        "masked": found.decrypted_value is None,
    }


def _day(value) -> str | None:
    return value.isoformat() if value else None


def export_customer(db, principal: AuthPrincipal, customer_id: int) -> dict:
    tenant_id = str(principal.tenant_id)
    customer = db.get(Customer, customer_id)
    if customer is None or customer.tenant_id != tenant_id:
        raise LookupError("customer_not_found")
    contacts = [
        {"channel": endpoint.channel, **(_opened(db, principal, endpoint.endpoint_token) or {})}
        for endpoint in db.scalars(
            select(CustomerEndpoint).where(
                CustomerEndpoint.tenant_id == tenant_id,
                CustomerEndpoint.customer_id == customer_id,
            )
        )
    ]
    receivables = [
        {
            "reference": row.source_record_id,
            "amount": str(row.amount),
            "currency": "MYR",
            "due_date": _day(row.expected_payment_date),
            "status": row.stage,
        }
        for row in db.scalars(
            select(SalesPipeline)
            .where(SalesPipeline.tenant_id == tenant_id, SalesPipeline.customer_id == customer_id)
            .order_by(SalesPipeline.expected_payment_date)
        )
    ]
    einvoices = [
        {
            "invoice_no": row.invoice_no,
            "amount": str(row.total_amount),
            "currency": row.currency or "MYR",
            "issue_date": _day(row.issue_date),
            "due_date": _day(row.due_date),
            "paid_on": _day(row.paid_at),
            "status": row.status,
        }
        for row in db.scalars(
            select(EInvoiceRecord)
            .where(
                EInvoiceRecord.tenant_id == tenant_id,
                EInvoiceRecord.buyer_customer_id == customer_id,
            )
            .order_by(EInvoiceRecord.id)
        )
    ]
    document = {
        "format": FORMAT,
        "generated_at": dt.datetime.now(dt.UTC).isoformat(),
        "subject": {
            "kind": "customer",
            "id": customer_id,
            "name": _opened(db, principal, customer.primary_name_token)
            or {"kind": "ORG", "value": customer.canonical_name, "masked": False},
        },
        "contacts": contacts,
        "receivables": receivables,
        "einvoices": einvoices,
    }
    write_workflow_event(
        db,
        event_type="data_export_prepared",
        actor_role=principal.role.value,
        actor_ref=principal.actor_ref,
        resource_type="customer",
        resource_id=str(customer_id),
        event_payload={"subject_kind": "customer", "subject_id": customer_id, "sections": SECTIONS},
        tenant_id=tenant_id,
    )
    db.commit()
    return document
