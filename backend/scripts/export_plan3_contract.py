"""Export the additive Plan 3 API, leaving the frozen Plan 1 contract untouched."""

import json
from pathlib import Path

from fastapi import FastAPI

from app.routes import customization, imports


def main():
    app = FastAPI(title="FinBrain OS - Plan 3 imports", version="3.0.0")
    app.include_router(customization.router)
    app.include_router(imports.router)
    document = app.openapi()
    document["paths"] = {
        k: v
        for k, v in document["paths"].items()
        if k.startswith(("/imports", "/settings/import-mappings"))
    }
    path = Path(__file__).resolve().parents[2] / "docs/api/topic-e-plan-3-openapi.json"
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(document['paths'])} paths to {path.name}")


if __name__ == "__main__":
    main()
