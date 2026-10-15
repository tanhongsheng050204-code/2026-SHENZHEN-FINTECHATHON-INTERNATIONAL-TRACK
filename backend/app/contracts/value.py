import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

from app.contracts.common import DataMode


class ValueMetric(BaseModel):
    key: str
    label: str
    value: str
    detail: str
    kind: Literal["measured", "estimate", "not_measured"] = Field(
        description="measured from records; an estimate says how; not_measured says why"
    )


class ValueReport(BaseModel):
    data_mode: DataMode
    as_of: dt.date
    synthetic: bool
    metrics: list[ValueMetric]
