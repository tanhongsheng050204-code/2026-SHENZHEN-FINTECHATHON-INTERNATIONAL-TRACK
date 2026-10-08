from enum import StrEnum

from pydantic import BaseModel, Field

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class DataMode(StrEnum):
    """Every contract response says whether its data is a canned stub or computed live."""

    STUB = "stub"
    LIVE = "live"


class AutonomyLevel(StrEnum):
    L0 = "L0"  # read and analyse
    L1 = "L1"  # internal drafts; a reviewer in the job function approves
    L2 = "L2"  # external action; the owner approves with AAL2 step-up
    L3 = "L3"  # money movement or regulatory filing; never executed by an agent


def autonomy_rank(level: AutonomyLevel) -> int:
    return int(level.value[1:])


class JobFunction(StrEnum):
    """The positions a person can hold. One person may hold several."""

    OWNER = "owner"
    OPERATIONS = "operations"
    FINANCE = "finance"
    SALES = "sales"
    CUSTOMER_SERVICE = "customer_service"
    MARKETING = "marketing"
    PROCUREMENT = "procurement"
    LOGISTICS = "logistics"
    PRODUCTION = "production"
    HR = "hr"
    COMPLIANCE = "compliance"


class OwaspAgenticRisk(StrEnum):
    """OWASP Top 10 for Agentic Applications (2026)."""

    ASI01 = "ASI01"  # Agent Goal Hijack
    ASI02 = "ASI02"  # Tool Misuse and Exploitation
    ASI03 = "ASI03"  # Identity and Privilege Abuse
    ASI04 = "ASI04"  # Agentic Supply Chain Vulnerabilities
    ASI05 = "ASI05"  # Unexpected Code Execution
    ASI06 = "ASI06"  # Memory & Context Poisoning
    ASI07 = "ASI07"  # Insecure Inter-Agent Communication
    ASI08 = "ASI08"  # Cascading Failures
    ASI09 = "ASI09"  # Human-Agent Trust Exploitation
    ASI10 = "ASI10"  # Rogue Agents


class EvidenceRef(BaseModel):
    label: str = Field(max_length=200)
    source: str = Field(max_length=200, description="e.g. einvoice:INV-1041")
