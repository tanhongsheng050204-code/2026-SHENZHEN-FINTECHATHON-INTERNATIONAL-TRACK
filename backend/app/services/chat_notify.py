"""Tell a team chat when items wait for review: Slack or WhatsApp.

The message says only how many items wait and for which positions, with a link to
the review inbox: no titles, amounts, customer names or anything people typed.
Deciding still happens in DuitDuit, with the usual approvals.

- Slack: an incoming webhook (SLACK_WEBHOOK_URL).
- WhatsApp: the WhatsApp Business Cloud API (WHATSAPP_ACCESS_TOKEN,
  WHATSAPP_PHONE_NUMBER_ID, WHATSAPP_RECIPIENT), with an approved template
  (WHATSAPP_TEMPLATE) when set. Business-initiated WhatsApp messages need an
  approved template; this connector has not been tested against a live account.

A message goes out only when the waiting counts change, at most once per check.
Every attempt is a "chat_notified" event on the company's workflow chain with the
channel, the outcome and the counts. In the shared demo company the message is
recorded as simulated and never sent.
"""

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.contracts.collaboration import ChatChannelStatus
from app.models import WorkflowAuditEntry
from app.services import review_inbox
from app.services.workflow_audit import chain_scalar, write_workflow_event

EVENT = "chat_notified"
CHANNELS = ("slack", "whatsapp")
_OPEN = ("pending", "awaiting_second_approval", "edited")
_POSITION = {
    "owner": "Owner",
    "operations": "Operations",
    "finance": "Finance",
    "sales": "Sales",
    "customer_service": "Customer service",
    "marketing": "Marketing",
    "procurement": "Purchasing",
    "logistics": "Logistics",
    "production": "Production",
    "hr": "HR",
    "compliance": "Compliance",
}


def _post(url: str, **kwargs) -> httpx.Response:
    return httpx.post(url, timeout=10, **kwargs)


def configured(channel: str) -> bool:
    settings = get_settings()
    if channel == "slack":
        return bool(settings.slack_webhook_url)
    return bool(
        settings.whatsapp_access_token
        and settings.whatsapp_phone_number_id
        and settings.whatsapp_recipient
    )


def serves(tenant_id: str) -> bool:
    """The channels belong to one company; no other company may see or use them."""
    target = get_settings().chat_notify_tenant_id
    return bool(target) and str(tenant_id) == target


def statuses(tenant_id: str) -> list[ChatChannelStatus]:
    mine = serves(tenant_id)
    enabled = get_settings().chat_notifications_enabled and mine
    return [
        ChatChannelStatus(channel=channel, configured=mine and configured(channel), enabled=enabled)
        for channel in CHANNELS
    ]


def waiting(db, tenant_id: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in review_inbox._replay(db, tenant_id).values():
        if item.action.status in _OPEN:
            job = item.action.reviewer_job_function.value
            counts[job] = counts.get(job, 0) + 1
    return dict(sorted(counts.items()))


def message(counts: dict[str, int]) -> str:
    total = sum(counts.values())
    parts = ", ".join(f"{_POSITION.get(job, job)} {n}" for job, n in counts.items())
    link = get_settings().app_public_url.rstrip("/") + "/inbox"
    if not total:
        return f"DuitDuit: nothing waits for review right now. Review inbox: {link}"
    return (
        f"DuitDuit: {total} item{'s' if total != 1 else ''} wait for review ({parts}). "
        f"Open the review inbox: {link}"
    )


def _send(channel: str, text: str) -> None:
    settings = get_settings()
    if channel == "slack":
        response = _post(settings.slack_webhook_url, json={"text": text})
    else:
        url = f"https://graph.facebook.com/v20.0/{settings.whatsapp_phone_number_id}/messages"
        body = {"messaging_product": "whatsapp", "to": settings.whatsapp_recipient}
        if settings.whatsapp_template:
            body |= {
                "type": "template",
                "template": {
                    "name": settings.whatsapp_template,
                    "language": {"code": settings.whatsapp_template_language},
                    "components": [
                        {"type": "body", "parameters": [{"type": "text", "text": text}]}
                    ],
                },
            }
        else:
            body |= {"type": "text", "text": {"body": text}}
        response = _post(
            url, json=body, headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"}
        )
    response.raise_for_status()


def notify(db, tenant_id: str, channel: str, counts: dict[str, int]) -> str:
    """Send one message on one channel; record and return the outcome."""
    settings = get_settings()
    if not serves(tenant_id) or not configured(channel):
        status = "not_configured"
    elif settings.demo_sign_in_enabled and tenant_id == settings.demo_tenant_id:
        status = "simulated"
    else:
        try:
            _send(channel, message(counts))
            status = "sent"
        except (httpx.HTTPError, ValueError):
            status = "failed"
    write_workflow_event(
        db,
        event_type=EVENT,
        actor_role="system",
        actor_ref="system:chat_notify",
        resource_type="chat_channel",
        resource_id=channel,
        event_payload={"status": status, "waiting": counts},
        tenant_id=tenant_id,
    )
    db.commit()
    return status


def _last_counts(db, tenant_id: str, channel: str) -> dict | None:
    payload = chain_scalar(
        db,
        select(WorkflowAuditEntry.event_payload)
        .where(
            WorkflowAuditEntry.tenant_id == tenant_id,
            WorkflowAuditEntry.event_type == EVENT,
            WorkflowAuditEntry.resource_id == channel,
        )
        .order_by(WorkflowAuditEntry.id.desc())
        .limit(1),
    )
    return None if payload is None else payload.get("waiting")


def run_due(db) -> int:
    """Message each configured channel when the waiting counts changed."""
    settings = get_settings()
    tenant_id = settings.chat_notify_tenant_id
    if not settings.chat_notifications_enabled or not tenant_id:
        return 0
    counts = waiting(db, tenant_id)
    sent = 0
    for channel in CHANNELS:
        if not configured(channel) or not counts:
            continue
        if _last_counts(db, tenant_id, channel) == counts:
            continue
        if notify(db, tenant_id, channel, counts) in ("sent", "simulated"):
            sent += 1
    return sent
