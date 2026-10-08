import datetime as dt

from pydantic import BaseModel, Field, field_validator, model_validator

from app.contracts.common import EMAIL_PATTERN, DataMode, JobFunction
from app.schemas import UserRole


class TeamMember(BaseModel):
    user_id: str
    display_name: str
    email_masked: str
    role: UserRole
    job_functions: list[JobFunction]
    active: bool
    mfa_enrolled: bool
    last_active_at: dt.datetime | None


class TeamResponse(BaseModel):
    data_mode: DataMode
    members: list[TeamMember]


class InvitationRequest(BaseModel):
    email: str = Field(max_length=254, pattern=EMAIL_PATTERN)
    role: UserRole
    job_functions: list[JobFunction] = Field(min_length=1, max_length=11)

    @field_validator("job_functions")
    @classmethod
    def _dedupe(cls, value: list[JobFunction]) -> list[JobFunction]:
        return list(dict.fromkeys(value))

    @model_validator(mode="after")
    def _owner_function_needs_owner_role(self) -> "InvitationRequest":
        if JobFunction.OWNER in self.job_functions and self.role != UserRole.OWNER_DIRECTOR:
            raise ValueError("owner_function_requires_owner_role")
        return self


class MemberUpdateRequest(BaseModel):
    role: UserRole | None = None
    job_functions: list[JobFunction] | None = Field(default=None, min_length=1, max_length=11)
    active: bool | None = None

    @field_validator("job_functions")
    @classmethod
    def _dedupe(cls, value: list[JobFunction] | None) -> list[JobFunction] | None:
        return None if value is None else list(dict.fromkeys(value))

    @model_validator(mode="after")
    def _at_least_one_change(self) -> "MemberUpdateRequest":
        if self.role is None and self.job_functions is None and self.active is None:
            raise ValueError("no_changes")
        return self


class MemberResponse(BaseModel):
    data_mode: DataMode
    member: TeamMember


class SignOutResponse(BaseModel):
    data_mode: DataMode
    user_id: str
    sessions_revoked: int
