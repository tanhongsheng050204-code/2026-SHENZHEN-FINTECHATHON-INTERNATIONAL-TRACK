from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.common import EMAIL_PATTERN, JobFunction
from app.schemas import UserRole


class AuthRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmailRequest(AuthRequest):
    email: str = Field(max_length=254, pattern=EMAIL_PATTERN)


class PasswordSignIn(EmailRequest):
    password: str = Field(min_length=1, max_length=256)


class SignUp(EmailRequest):
    password: str = Field(min_length=12, max_length=256)


class CodeRequest(AuthRequest):
    code: str = Field(pattern=r"^\d{6,8}$")


class PasswordRequest(AuthRequest):
    password: str = Field(min_length=12, max_length=256)


class TotpVerify(AuthRequest):
    factor_id: UUID
    challenge_id: UUID
    code: str = Field(pattern=r"^\d{6}$")


class CompanySetup(AuthRequest):
    company_name: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,59}$")


class SessionResponse(BaseModel):
    state: Literal[
        "email_code_required",
        "password_required",
        "mfa_enrollment_required",
        "mfa_required",
        "company_setup_required",
        "authenticated",
    ]
    csrf_token: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    role: UserRole | None = None
    job_functions: list[JobFunction] = Field(default_factory=list)
    aal: Literal["aal1", "aal2"] = "aal1"


class TotpEnrollment(BaseModel):
    factor_id: str
    qr_code: str
    secret: str
    uri: str


class TotpChallenge(BaseModel):
    challenge_id: str
