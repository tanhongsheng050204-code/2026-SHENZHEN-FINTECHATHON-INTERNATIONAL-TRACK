"""Saved views: a set of filters on the customer list or the collections board.

A view holds filters only, never free text; the screen names it from its filters.
A private view is seen by the person who saved it, a shared one by everyone who can
open that screen. Views are stored on the workflow chain ("saved_view_saved",
"saved_view_removed", latest event wins). The person who saved a view, or the owner,
can remove it.
"""

import datetime as dt
import secrets

from sqlalchemy import select

from app.auth.principal import AuthPrincipal
from app.contracts.collaboration import SavedView, SavedViewRequest
from app.models import WorkflowAuditEntry
from app.schemas import UserRole
from app.services.workflow_audit import chain_scalars, write_workflow_event

SAVED, REMOVED = "saved_view_saved", "saved_view_removed"
MAX_VIEWS_PER_PERSON = 20


class ViewError(ValueError):
    def __init__(self, code: str, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def _current(db, tenant_id: str) -> dict[str, tuple[WorkflowAuditEntry, dt.datetime]]:
    views: dict[str, tuple[WorkflowAuditEntry, dt.datetime] | None] = {}
    for row in chain_scalars(
        db,
        select(WorkflowAuditEntry)
        .where(
            WorkflowAuditEntry.tenant_id == tenant_id,
            WorkflowAuditEntry.event_type.in_((SAVED, REMOVED)),
        )
        .order_by(WorkflowAuditEntry.id),
    ):
        if row.event_type == REMOVED:
            views[row.resource_id] = None
        else:
            created = (
                row.created_at if row.created_at.tzinfo else row.created_at.replace(tzinfo=dt.UTC)
            )
            views[row.resource_id] = (row, created)
    return {key: value for key, value in views.items() if value is not None}


def views(db, principal: AuthPrincipal, screen: str) -> list[SavedView]:
    me = str(principal.user_id)
    found = []
    for view_id, (row, created) in _current(db, str(principal.tenant_id)).items():
        payload = row.event_payload
        if payload["screen"] != screen or not (payload["shared"] or row.actor_ref == me):
            continue
        found.append(SavedView(id=view_id, mine=row.actor_ref == me, created_at=created, **payload))
    return found


def save(db, principal: AuthPrincipal, request: SavedViewRequest) -> SavedView:
    tenant_id = str(principal.tenant_id)
    mine = [
        row
        for row, _ in _current(db, tenant_id).values()
        if row.actor_ref == str(principal.user_id)
    ]
    if len(mine) >= MAX_VIEWS_PER_PERSON:
        raise ViewError("too_many_saved_views", 409)
    view_id = "view_" + secrets.token_hex(6)
    write_workflow_event(
        db,
        event_type=SAVED,
        actor_role=principal.role.value,
        actor_ref=str(principal.user_id),
        resource_type="saved_view",
        resource_id=view_id,
        event_payload=request.model_dump(mode="json"),
        tenant_id=tenant_id,
    )
    db.commit()
    return next(v for v in views(db, principal, request.screen) if v.id == view_id)


def remove(db, principal: AuthPrincipal, view_id: str) -> None:
    found = _current(db, str(principal.tenant_id)).get(view_id)
    if found is None:
        raise ViewError("view_not_found", 404)
    row, _ = found
    if row.actor_ref != str(principal.user_id):
        # Someone else's private view does not exist for this person.
        if not row.event_payload["shared"]:
            raise ViewError("view_not_found", 404)
        if principal.role != UserRole.OWNER_DIRECTOR:
            raise ViewError("not_your_view", 403)
    write_workflow_event(
        db,
        event_type=REMOVED,
        actor_role=principal.role.value,
        actor_ref=str(principal.user_id),
        resource_type="saved_view",
        resource_id=view_id,
        event_payload={},
        tenant_id=str(principal.tenant_id),
    )
    db.commit()
