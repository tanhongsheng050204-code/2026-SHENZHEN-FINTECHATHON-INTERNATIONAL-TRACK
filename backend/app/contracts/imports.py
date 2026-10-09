"""Additive Plan 3 contract. Preview/error payloads never echo source cell values."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.contracts.common import DataMode
from app.contracts.customization import ImportSchema


class CsvImportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csv_text: str = Field(min_length=1, max_length=2_000_000, repr=False)
    mapping_id: str | None = Field(default=None, max_length=80)


class ImportIssue(BaseModel):
    row: int
    field: str
    code: str


class CsvImportPreview(BaseModel):
    data_mode: DataMode = DataMode.LIVE
    schema_name: ImportSchema
    mapping_id: str | None
    fingerprint: str
    total_rows: int
    accepted_rows: int
    duplicate_rows: int
    issues: list[ImportIssue]
    can_commit: bool


class CsvImportResult(BaseModel):
    data_mode: DataMode = DataMode.LIVE
    schema_name: ImportSchema
    batch_id: str
    imported_rows: int
    duplicate_rows: int
    replayed: bool
    synthetic: bool


class ImportBatchView(BaseModel):
    id: str
    schema_name: ImportSchema
    imported_rows: int
    duplicate_rows: int
    synthetic: bool
    created_at: datetime


class ImportBatchesResponse(BaseModel):
    data_mode: DataMode = DataMode.LIVE
    batches: list[ImportBatchView]


class ImportSchemaView(BaseModel):
    schema_name: ImportSchema
    fields: list[str]
    required_fields: list[str]
    writer_jobs: list[str]


class ImportSchemasResponse(BaseModel):
    data_mode: DataMode = DataMode.LIVE
    schemas: list[ImportSchemaView]
