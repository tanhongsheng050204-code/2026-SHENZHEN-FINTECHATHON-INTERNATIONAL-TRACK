"""Supabase Auth is called exclusively by the API, never by browser code."""

import httpx
from fastapi import HTTPException

from app.config import get_settings


class AuthProvider:
    def call(self, method: str, path: str, *, payload=None, token=None, admin=False) -> dict:
        settings = get_settings()
        key = settings.supabase_service_role_key if admin else settings.supabase_anon_key
        if not settings.supabase_url or not key:
            raise HTTPException(503, "supabase_auth_not_configured")
        headers = {"apikey": key, "Authorization": f"Bearer {token or key}"}
        try:
            with httpx.Client(timeout=12, follow_redirects=False) as client:
                response = client.request(
                    method,
                    f"{settings.supabase_url.rstrip('/')}/auth/v1{path}",
                    headers=headers,
                    json=payload,
                )
        except httpx.HTTPError as error:
            raise HTTPException(503, "auth_provider_unavailable") from error
        if response.status_code >= 400:
            try:
                provider_code = response.json().get("error_code")
            except (ValueError, AttributeError):
                provider_code = None
            if provider_code == "insufficient_aal":
                raise HTTPException(403, "step_up_required")
            code = (
                429 if response.status_code == 429 else 503 if response.status_code >= 500 else 400
            )
            # Never relay provider bodies: they can contain email addresses or tokens.
            raise HTTPException(code, "auth_rate_limited" if code == 429 else "auth_request_failed")
        if not response.content:
            return {}
        try:
            data = response.json()
        except ValueError as error:
            raise HTTPException(503, "auth_provider_invalid_response") from error
        if not isinstance(data, dict):
            raise HTTPException(503, "auth_provider_invalid_response")
        return data


provider = AuthProvider()
