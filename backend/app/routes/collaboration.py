"""Team work around the review inbox and receivables: comments and @mentions, the
collections board, automations, saved views and chat notifications."""

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import require_roles, require_step_up
from app.auth.principal import AuthPrincipal
from app.contracts.collaboration import (
    ApiKeyCall,
    ApiKeyCreated,
    ApiKeyRequest,
    ApiKeysResponse,
    ApiKeyView,
    Automation,
    AutomationRequest,
    AutomationRunResponse,
    AutomationRunsResponse,
    AutomationsResponse,
    ChatChannel,
    ChatNotificationsResponse,
    ChatTestResponse,
    CollectionsBoardResponse,
    CommentRequest,
    CommentsResponse,
    HoldRequest,
    HoldsResponse,
    MentionsResponse,
    ReminderProposalResponse,
    ReviewComment,
    SavedView,
    SavedViewRequest,
    SavedViewScreen,
    SavedViewsResponse,
)
from app.contracts.common import DataMode
from app.db import get_db
from app.schemas import UserRole
from app.services import (
    api_keys,
    automations,
    business_day,
    chat_notify,
    collections,
    receivable_holds,
    review_comments,
    saved_views,
)

router = APIRouter(tags=["collaboration"])

_ALL_ROLES = tuple(UserRole)
_MONEY_READ = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR, UserRole.COMPLIANCE)
_MONEY_WORK = (UserRole.FINANCE_OPS, UserRole.OWNER_DIRECTOR)


def _refuse(error) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.code)


def _day(db, principal: AuthPrincipal):
    return business_day.today(db, principal.tenant_id)


@router.get("/review-inbox/{action_id}/comments", response_model=CommentsResponse)
def list_comments(
    action_id: str,
    principal: AuthPrincipal = Depends(require_roles(*_ALL_ROLES)),
    db: Session = Depends(get_db),
) -> CommentsResponse:
    try:
        rows = review_comments.comments(db, principal, action_id)
    except review_comments.CommentError as error:
        raise _refuse(error) from error
    return CommentsResponse(data_mode=DataMode.LIVE, comments=rows)


@router.post("/review-inbox/{action_id}/comments", response_model=ReviewComment)
def add_comment(
    action_id: str,
    request: CommentRequest,
    principal: AuthPrincipal = Depends(require_roles(*_ALL_ROLES)),
    db: Session = Depends(get_db),
) -> ReviewComment:
    try:
        return review_comments.add(db, principal, action_id, request.text, request.mentions)
    except review_comments.CommentError as error:
        raise _refuse(error) from error


@router.get("/mentions", response_model=MentionsResponse)
def my_mentions(
    principal: AuthPrincipal = Depends(require_roles(*_ALL_ROLES)),
    db: Session = Depends(get_db),
) -> MentionsResponse:
    return MentionsResponse(
        data_mode=DataMode.LIVE, mentions=review_comments.mentions_for(db, principal)
    )


@router.get("/collections/board", response_model=CollectionsBoardResponse)
def collections_board(
    principal: AuthPrincipal = Depends(require_roles(*_MONEY_READ)),
    db: Session = Depends(get_db),
) -> CollectionsBoardResponse:
    return collections.board(db, principal, _day(db, principal))


@router.post("/collections/{ref}/reminder", response_model=ReminderProposalResponse)
def collections_reminder(
    ref: str,
    principal: AuthPrincipal = Depends(require_roles(*_MONEY_WORK)),
    db: Session = Depends(get_db),
) -> ReminderProposalResponse:
    try:
        action_id = collections.propose_reminder(db, principal, ref, _day(db, principal))
    except collections.BoardError as error:
        raise _refuse(error) from error
    return ReminderProposalResponse(data_mode=DataMode.LIVE, action_id=action_id)


@router.get("/collections/holds", response_model=HoldsResponse)
def collections_holds(
    principal: AuthPrincipal = Depends(require_roles(*_MONEY_READ)),
    db: Session = Depends(get_db),
) -> HoldsResponse:
    return HoldsResponse(
        data_mode=DataMode.LIVE, holds=collections.holds(db, principal, _day(db, principal))
    )


@router.put("/collections/holds/{target}", status_code=200)
def set_collections_hold(
    target: str,
    request: HoldRequest,
    principal: AuthPrincipal = Depends(require_roles(*_MONEY_WORK)),
    db: Session = Depends(get_db),
) -> dict:
    try:
        collections.set_hold(db, principal, target, request, _day(db, principal))
    except (collections.BoardError, receivable_holds.HoldError) as error:
        raise _refuse(error) from error
    return {"target": target, "kind": request.kind}


@router.delete("/collections/holds/{target}", status_code=204)
def clear_collections_hold(
    target: str,
    principal: AuthPrincipal = Depends(require_roles(*_MONEY_WORK)),
    db: Session = Depends(get_db),
) -> None:
    try:
        receivable_holds.clear(db, principal, target)
    except receivable_holds.HoldError as error:
        raise _refuse(error) from error


@router.get("/automations", response_model=AutomationsResponse)
def list_automations(
    principal: AuthPrincipal = Depends(require_roles(*_MONEY_READ)),
    db: Session = Depends(get_db),
) -> AutomationsResponse:
    return AutomationsResponse(
        data_mode=DataMode.LIVE,
        automations=automations.automations(db, str(principal.tenant_id)),
    )


@router.post("/automations", response_model=Automation)
def save_automation(
    request: AutomationRequest,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> Automation:
    try:
        return automations.save(db, principal, request)
    except automations.AutomationError as error:
        raise _refuse(error) from error


@router.delete("/automations/{automation_id}", status_code=204)
def remove_automation(
    automation_id: str,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> None:
    try:
        automations.remove(db, principal, automation_id)
    except automations.AutomationError as error:
        raise _refuse(error) from error


@router.post("/automations/run", response_model=AutomationRunResponse)
def run_automations(
    principal: AuthPrincipal = Depends(require_roles(*_MONEY_WORK)),
    db: Session = Depends(get_db),
) -> AutomationRunResponse:
    return AutomationRunResponse(
        data_mode=DataMode.LIVE,
        proposals=automations.run(db, str(principal.tenant_id), _day(db, principal)),
    )


@router.get("/automations/{automation_id}/runs", response_model=AutomationRunsResponse)
def automation_runs(
    automation_id: str,
    principal: AuthPrincipal = Depends(require_roles(*_MONEY_READ)),
    db: Session = Depends(get_db),
) -> AutomationRunsResponse:
    try:
        rows = automations.runs(db, str(principal.tenant_id), automation_id)
    except automations.AutomationError as error:
        raise _refuse(error) from error
    return AutomationRunsResponse(data_mode=DataMode.LIVE, runs=rows)


def _check_screen(principal: AuthPrincipal, screen: str) -> None:
    if screen == "collections" and principal.role not in _MONEY_READ:
        raise HTTPException(status_code=403, detail="insufficient_role")


@router.get("/saved-views", response_model=SavedViewsResponse)
def list_saved_views(
    screen: SavedViewScreen = Query(),
    principal: AuthPrincipal = Depends(require_roles(*_ALL_ROLES)),
    db: Session = Depends(get_db),
) -> SavedViewsResponse:
    _check_screen(principal, screen)
    return SavedViewsResponse(
        data_mode=DataMode.LIVE, views=saved_views.views(db, principal, screen)
    )


@router.post("/saved-views", response_model=SavedView)
def save_view(
    request: SavedViewRequest,
    principal: AuthPrincipal = Depends(require_roles(*_ALL_ROLES)),
    db: Session = Depends(get_db),
) -> SavedView:
    _check_screen(principal, request.screen)
    try:
        return saved_views.save(db, principal, request)
    except saved_views.ViewError as error:
        raise _refuse(error) from error


@router.delete("/saved-views/{view_id}", status_code=204)
def remove_view(
    view_id: str,
    principal: AuthPrincipal = Depends(require_roles(*_ALL_ROLES)),
    db: Session = Depends(get_db),
) -> None:
    try:
        saved_views.remove(db, principal, view_id)
    except saved_views.ViewError as error:
        raise _refuse(error) from error


@router.get("/notifications/channels", response_model=ChatNotificationsResponse)
def chat_channels(
    principal: AuthPrincipal = Depends(require_roles(*_MONEY_READ)),
) -> ChatNotificationsResponse:
    return ChatNotificationsResponse(
        data_mode=DataMode.LIVE, channels=chat_notify.statuses(str(principal.tenant_id))
    )


@router.post("/notifications/test", response_model=ChatTestResponse)
def chat_test(
    channel: ChatChannel = Body(embed=True),
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> ChatTestResponse:
    tenant_id = str(principal.tenant_id)
    status = chat_notify.notify(db, tenant_id, channel, chat_notify.waiting(db, tenant_id))
    return ChatTestResponse(data_mode=DataMode.LIVE, channel=channel, status=status)


@router.get("/api-keys", response_model=ApiKeysResponse)
def list_api_keys(
    principal: AuthPrincipal = Depends(require_roles(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> ApiKeysResponse:
    rows = api_keys.keys(db, str(principal.tenant_id))
    return ApiKeysResponse(data_mode=DataMode.LIVE, keys=[_key_view(k) for k in rows])


def _key_view(key) -> ApiKeyView:
    fields = vars(key) | {"recent_calls": [ApiKeyCall(**call) for call in key.recent_calls]}
    return ApiKeyView(**fields)


@router.post("/api-keys", response_model=ApiKeyCreated)
def create_api_key(
    request: ApiKeyRequest | None = Body(default=None),
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> ApiKeyCreated:
    try:
        key, secret = api_keys.create(db, principal, request)
    except api_keys.KeyError_ as error:
        raise _refuse(error) from error
    return ApiKeyCreated(data_mode=DataMode.LIVE, key=_key_view(key), secret=secret)


@router.delete("/api-keys/{key_id}", status_code=204)
def revoke_api_key(
    key_id: str,
    principal: AuthPrincipal = Depends(require_step_up(UserRole.OWNER_DIRECTOR)),
    db: Session = Depends(get_db),
) -> None:
    try:
        api_keys.revoke(db, principal, key_id)
    except api_keys.KeyError_ as error:
        raise _refuse(error) from error
