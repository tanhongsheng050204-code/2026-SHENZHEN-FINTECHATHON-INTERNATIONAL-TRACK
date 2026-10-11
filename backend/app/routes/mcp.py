"""DuitDuit as a read-only MCP server, so Claude or ChatGPT can answer from it.

Model Context Protocol over Streamable HTTP, answered as plain JSON: POST /mcp
with "Authorization: Bearer ddk_…", a company API key (app.services.api_keys).
Five tools read the cash forecast, the forecast check, the review inbox, the
collections board and financing matches. None writes anything: changes still go
through the review inbox, with its approvals, in DuitDuit itself.

What the tools return is figures, titles and masked labels. Contact details and
restored names never leave, because the key's session may not disclose tokens.
Each call is recorded on the company's chain as the tool's name and the key id.
"""

import datetime as dt
import json
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.db import get_db, set_rls_context
from app.security import rate_limit
from app.services import api_keys, cashflow_engine, collections, forecast_check, live_agents
from app.services.cashflow import basis_for
from app.services.workflow_audit import write_workflow_event

router = APIRouter(tags=["mcp"], include_in_schema=False)

PROTOCOL = "2025-06-18"
_per_key = rate_limit.counter("mcp", 60)
# Before a key is checked, so guessing keys is slow too.
_per_address = rate_limit.counter("mcp-address", 120)
MAX_BATCH = 10

TOOLS = [
    {
        "name": "get_cash_forecast",
        "description": "The company's cash forecast: opening balance, minimum, lowest likely "
        "point, any shortfall and today's alerts. Figures in ringgit.",
        "inputSchema": {
            "type": "object",
            "properties": {"horizon_days": {"type": "integer", "enum": [30, 60, 90]}},
        },
    },
    {
        "name": "get_forecast_check",
        "description": "How past forecasts compared with the bank balance; says when this "
        "is not measured yet.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_review_inbox",
        "description": "Items waiting for a person's decision: title, approval level, "
        "position and amount. Read-only: decisions are made in DuitDuit.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_collections_board",
        "description": "Unpaid invoices by column (later, due soon, overdue, reminder, paid) "
        "with counts and totals.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_financing_matches",
        "description": "Financing products checked against the company's records: "
        "eligibility, fit score and the next step. Not offers of credit.",
        "inputSchema": {
            "type": "object",
            "properties": {"jurisdiction": {"type": "string", "enum": ["MY", "CN"]}},
        },
    },
]


def _plain(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _forecast(db, principal, args):
    horizon = args.get("horizon_days", 90)
    if horizon not in (30, 60, 90):
        raise ValueError("horizon_days must be 30, 60 or 90")
    today = dt.date.today()
    forecast = cashflow_engine.build_forecast(
        basis_for(db, principal, today), horizon_days=horizon, as_of=today
    )
    low = min(forecast.points, key=lambda p: p.likely)
    return {
        "data_mode": forecast.data_mode.value,
        "as_of": forecast.as_of,
        "horizon_days": horizon,
        "opening_balance": forecast.opening_balance,
        "minimum_balance": forecast.minimum_balance,
        "lowest_likely": {"day": low.day, "date": low.date, "balance": low.likely},
        "shortfall": forecast.shortfall.model_dump() if forecast.shortfall else None,
        "alerts": [{"title": a.title, "detail": a.detail} for a in forecast.alerts],
    }


def _check(db, principal, args):
    data_mode = basis_for(db, principal, dt.date.today()).data_mode
    return forecast_check.report(db, str(principal.tenant_id), data_mode).model_dump()


def _inbox(db, principal, args):
    _, actions = live_agents.inbox_for(db, principal, None)
    waiting = [a for a in actions if a.status in ("pending", "awaiting_second_approval", "edited")]
    return {
        "waiting": len(waiting),
        "items": [
            {
                "title": a.title,
                "level": a.autonomy_level.value,
                "position": a.reviewer_job_function.value,
                "status": a.status,
                "amount": a.amount,
            }
            for a in waiting
        ],
    }


def _board(db, principal, args):
    board = collections.board(db, principal, dt.date.today())
    return {
        "data_mode": board.data_mode.value,
        "columns": [
            {"stage": c.stage, "count": len(c.cards), "total": c.total} for c in board.columns
        ],
    }


def _financing(db, principal, args):
    from app.routes.financing import _profile
    from app.stubs import financing as stub

    jurisdiction = args.get("jurisdiction", "MY")
    if jurisdiction not in ("MY", "CN"):
        raise ValueError("jurisdiction must be MY or CN")
    result = stub.matches(jurisdiction, _profile(db, principal))
    return {
        "disclaimer": result.disclaimer,
        "matches": [
            {
                "product": m.product.name,
                "eligible": m.eligible,
                "fit_score": m.fit_score,
                "explanation": m.explanation,
                "next_step": m.next_step,
            }
            for m in result.matches
        ],
    }


HANDLERS = {
    "get_cash_forecast": _forecast,
    "get_forecast_check": _check,
    "get_review_inbox": _inbox,
    "get_collections_board": _board,
    "get_financing_matches": _financing,
}


def _error(request_id, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _answer(db, principal, key_id: str, message: dict) -> dict | None:
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _error(None, -32600, "Invalid request")
    method, request_id = message.get("method"), message.get("id")
    if request_id is None:
        return None  # a notification, such as notifications/initialized
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "duitduit", "version": "1.0"},
                "instructions": "Read-only access to one company's DuitDuit figures. "
                "Nothing here can send, pay or change anything.",
            },
        }
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") or {}
        name, args = params.get("name"), params.get("arguments") or {}
        handler = HANDLERS.get(name)
        if handler is None:
            return _error(request_id, -32602, f"Unknown tool: {name}")
        try:
            payload = _plain(handler(db, principal, args))
            is_error = False
        except ValueError as problem:
            payload, is_error = {"error": str(problem)}, True
        write_workflow_event(
            db,
            event_type="mcp_tool_called",
            actor_role="api_key",
            actor_ref=principal.actor_ref,
            resource_type="api_key",
            resource_id=key_id,
            event_payload={"tool": name},
            tenant_id=str(principal.tenant_id),
        )
        db.commit()
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
                "structuredContent": payload,
                "isError": is_error,
            },
        }
    return _error(request_id, -32601, f"Method not found: {method}")


@router.post("/mcp")
async def mcp(request: Request, db: Session = Depends(get_db)):
    _per_address(rate_limit.client_address(request))
    header = request.headers.get("authorization", "")
    found = api_keys.authenticate(db, header.removeprefix("Bearer ").strip())
    if found is None:
        return JSONResponse(
            {"detail": "invalid_api_key"},
            status_code=401,
            headers={"WWW-Authenticate": 'Bearer realm="duitduit"'},
        )
    principal, key_id = found
    # Read with the owner's role, but never restore protected values.
    db.info["finbrain_disclosure_allowed"] = False
    set_rls_context(
        db,
        user_id=str(principal.user_id),
        user_role=principal.role.value,
        actor_ref=principal.actor_ref,
        tenant_id=str(principal.tenant_id),
    )
    if not api_keys.holder_still_owner(db, principal):
        return JSONResponse({"detail": "invalid_api_key"}, status_code=401)
    try:
        body = json.loads(await request.body())
    except ValueError:
        return JSONResponse(_error(None, -32700, "Parse error"), status_code=400)
    messages = body if isinstance(body, list) else [body]
    if len(messages) > MAX_BATCH:
        return JSONResponse(_error(None, -32600, "Too many messages in one batch"), status_code=400)
    for _ in messages:
        _per_key(f"key:{key_id}")  # every message counts against the key's limit
    if isinstance(body, list):
        answers = [a for a in (_answer(db, principal, key_id, m) for m in body) if a is not None]
        return JSONResponse(answers) if answers else Response(status_code=202)
    answer = _answer(db, principal, key_id, body)
    return JSONResponse(answer) if answer is not None else Response(status_code=202)


@router.get("/mcp")
def mcp_stream() -> Response:
    # No server-initiated messages: this server only answers requests.
    return Response(status_code=405, headers={"Allow": "POST"})
