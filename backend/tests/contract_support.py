from uuid import UUID

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.principal import AuthPrincipal
from app.db import get_db
from app.schemas import UserRole
from tests.auth_support import TENANT_A, principal

# Demo members beyond the four role accounts in tests.auth_support.
OPERATIONS_MANAGER = UUID("50000000-0000-0000-0000-000000000005")
PURCHASING_STORES = UUID("60000000-0000-0000-0000-000000000006")
MARKETING_EXEC = UUID("70000000-0000-0000-0000-000000000007")


def _no_database():
    yield None


def _client(router: APIRouter, current: AuthPrincipal | None) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = _no_database
    if current is not None:
        app.dependency_overrides[get_current_user] = lambda: current
    return TestClient(app)


def client_for(router: APIRouter, role: UserRole | None = UserRole.OWNER_DIRECTOR) -> TestClient:
    """A client signed in as the demo account for `role`; role=None is unauthenticated."""
    return _client(router, principal(role) if role is not None else None)


def client_as(router: APIRouter, user_id: UUID, role: UserRole) -> TestClient:
    """A client signed in as a specific demo member."""
    current = AuthPrincipal(
        user_id=user_id, email=f"{user_id}@finbrain.test", role=role, tenant_id=TENANT_A
    )
    return _client(router, current)
