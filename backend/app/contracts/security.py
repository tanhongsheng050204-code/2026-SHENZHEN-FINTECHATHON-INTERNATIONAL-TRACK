"""Security activity, sign-ins, the incident register and the data protection officer."""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.contracts.common import DataMode

# ── Sign-ins and the security feed ──────────────────────────────────────────


class SignIn(BaseModel):
    at: dt.datetime
    browser: str
    system: str
    method: str
    new_device: bool


class SignInsResponse(BaseModel):
    data_mode: DataMode
    sign_ins: list[SignIn]


Severity = Literal["info", "warning", "critical"]


class SecurityEvent(BaseModel):
    at: dt.datetime
    kind: str
    severity: Severity
    title: str
    actor_role: str


class SecurityActivityResponse(BaseModel):
    data_mode: DataMode
    events: list[SecurityEvent]


# ── Incident register ───────────────────────────────────────────────────────

IncidentKind = Literal[
    "unauthorized_access",
    "lost_or_stolen_device",
    "data_sent_to_wrong_person",
    "system_compromise",
    "vendor_breach",
    "other",
]
DataKind = Literal[
    "contact_details",
    "identity_numbers",
    "financial_records",
    "employee_records",
    "credentials",
]
IncidentStepName = Literal[
    "contained", "assessed", "commissioner_notified", "individuals_notified", "closed"
]


class IncidentRequest(BaseModel):
    """Kinds and numbers only: no free text, so no personal data reaches the record."""

    kind: IncidentKind
    data_kinds: list[DataKind] = Field(min_length=1, max_length=5)
    people_affected: int = Field(ge=0, le=10_000_000)
    significant_harm: bool
    detected_on: dt.date

    @field_validator("detected_on")
    @classmethod
    def _not_in_the_future(cls, value: dt.date) -> dt.date:
        if value > dt.date.today():
            raise ValueError("detected_in_the_future")
        return value


class ChecklistItem(BaseModel):
    step: IncidentStepName
    required: bool
    done: bool
    done_at: dt.datetime | None = None
    done_by_role: str | None = None


class Incident(IncidentRequest):
    id: str
    opened_at: dt.datetime
    opened_by_role: str
    status: Literal["open", "closed"]
    checklist: list[ChecklistItem]


class IncidentsResponse(BaseModel):
    data_mode: DataMode
    incidents: list[Incident]


class IncidentStepRequest(BaseModel):
    step: IncidentStepName


class NoticeRequest(BaseModel):
    audience: Literal["commissioner", "individuals"]


class NoticeResponse(BaseModel):
    data_mode: DataMode
    action_id: str


# ── Data protection officer ─────────────────────────────────────────────────


class DpoRequest(BaseModel):
    user_id: str = Field(min_length=36, max_length=36)


class Officer(BaseModel):
    user_id: str
    display_name: str
    email_masked: str
    role: str


class DpoResponse(BaseModel):
    data_mode: DataMode
    officer: Officer | None
