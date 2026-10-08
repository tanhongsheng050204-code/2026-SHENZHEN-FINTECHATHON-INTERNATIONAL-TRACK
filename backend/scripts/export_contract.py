"""Write the Topic E API contract (OpenAPI) to docs/api/topic-e-contract.json.

Run from backend/: uv run python -m scripts.export_contract
The frontend builds against this file; tests/test_contract_openapi.py fails when it drifts.
"""

import json
from pathlib import Path

from fastapi import FastAPI

from app.routes import (
    agents,
    cashflow,
    customization,
    financing,
    inbox,
    passports,
    positions,
    team,
    trust,
)
from app.routes import settings as settings_routes

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "docs" / "api" / "topic-e-contract.json"
CONTRACT_ROUTERS = (
    cashflow.router,
    agents.router,
    inbox.router,
    positions.router,
    financing.router,
    passports.router,
    trust.router,
    team.router,
    settings_routes.router,
    customization.router,
)


def build_contract_app() -> FastAPI:
    app = FastAPI(title="FinBrain OS Topic E contract", version="2026-10-09")
    for router in CONTRACT_ROUTERS:
        app.include_router(router)
    return app


def render_contract() -> str:
    document = build_contract_app().openapi()
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main() -> None:
    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTRACT_PATH.write_text(render_contract(), encoding="utf-8", newline="\n")
    print(f"wrote {CONTRACT_PATH}")


if __name__ == "__main__":
    main()
