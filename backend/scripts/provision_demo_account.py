"""Create the shared demo account for the synthetic company, for the one-click demo sign-in.

Run once, by the person who holds the production keys:

    python -m scripts.provision_demo_account --email demo-owner@<your-domain> --out demo-account.env

It:
1. creates a confirmed Supabase user with a long random password (no email is sent);
2. makes it the owner of the synthetic demo company (it is never added to any other company);
3. enrols an authenticator for it and checks one code;
4. writes DEMO_SIGN_IN_ENABLED, DEMO_EMAIL, DEMO_PASSWORD and DEMO_TOTP_SECRET to --out.

The secrets go only into that file. Copy them into the API's environment, then delete the file.
Nothing is printed except ids and next steps.
"""

from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path

from app.auth import demo
from app.auth.provider import provider
from app.config import get_settings
from app.db import SessionLocal
from app.models import AuthUserRole, Tenant
from app.schemas import UserRole


def _create_user(email: str, password: str) -> str:
    user = provider.call(
        "POST",
        "/admin/users",
        admin=True,
        payload={"email": email, "password": password, "email_confirm": True},
    )
    return user["id"]


def _enrol_authenticator(email: str, password: str) -> str:
    token = provider.call(
        "POST", "/token?grant_type=password", payload={"email": email, "password": password}
    )["access_token"]
    factor = provider.call(
        "POST",
        "/factors",
        token=token,
        payload={"factor_type": "totp", "friendly_name": "DuitDuit demo"},
    )
    secret = factor["totp"]["secret"]
    challenge = provider.call("POST", f"/factors/{factor['id']}/challenge", payload={}, token=token)
    provider.call(
        "POST",
        f"/factors/{factor['id']}/verify",
        token=token,
        payload={"challenge_id": challenge["id"], "code": demo.totp(secret)},
    )
    return secret


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--email", required=True, help="An address on a domain you control")
    parser.add_argument("--out", required=True, type=Path, help="New file for the four settings")
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit(f"{args.out} already exists; choose a new file.")
    tenant_id = get_settings().demo_tenant_id

    # Memberships are written as the database owner, like other operator scripts: the
    # scoped worker role has no grant on user_roles.
    with SessionLocal() as db:
        if db.get(Tenant, tenant_id) is None:
            raise SystemExit("The synthetic demo company is missing. Run seed.topic_e first.")
        password = secrets.token_urlsafe(32)
        user_id = _create_user(args.email, password)
        db.merge(
            AuthUserRole(
                user_id=user_id,
                tenant_id=tenant_id,
                user_role=UserRole.OWNER_DIRECTOR.value,
                job_functions=["owner"],
                active=True,
                mfa_enrolled=True,
                display_name="Demo owner (synthetic company)",
            )
        )
        db.commit()

    totp_secret = _enrol_authenticator(args.email, password)
    descriptor = os.open(args.out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(
            "DEMO_SIGN_IN_ENABLED=true\n"
            f"DEMO_EMAIL={args.email}\n"
            f"DEMO_PASSWORD={password}\n"
            f"DEMO_TOTP_SECRET={totp_secret}\n"
        )
    print(f"Demo owner {user_id} added to company {tenant_id}.")
    print(f"Settings written to {args.out}. Add them to the API environment, then delete the file.")


if __name__ == "__main__":
    main()
