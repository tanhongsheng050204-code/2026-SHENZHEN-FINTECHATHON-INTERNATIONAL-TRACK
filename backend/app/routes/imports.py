import datetime as dt

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, require_step_up
from app.auth.principal import AuthPrincipal
from app.contracts.customization import IMPORT_FIELDS, ImportSchema
from app.contracts.imports import (
    CsvImportPreview,
    CsvImportRequest,
    CsvImportResult,
    ImportBatchesResponse,
    ImportBatchView,
    ImportSchemasResponse,
    ImportSchemaView,
)
from app.db import get_db
from app.models import BusinessImportBatch
from app.schemas import UserRole
from app.services import alerts
from app.services.business_imports import WRITER_JOBS, authorize, commit_import, prepare

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("/schemas", response_model=ImportSchemasResponse)
def schemas(_principal: CurrentUser):
    return ImportSchemasResponse(
        schemas=[
            ImportSchemaView(
                schema_name=schema,
                fields=sorted(fields),
                required_fields=sorted(required),
                writer_jobs=list(WRITER_JOBS[schema]),
            )
            for schema, (fields, required) in IMPORT_FIELDS.items()
        ]
    )


@router.get("/batches", response_model=ImportBatchesResponse)
def batches(
    principal: CurrentUser,
    schema_name: ImportSchema | None = None,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(BusinessImportBatch).where(
        BusinessImportBatch.tenant_id == str(principal.tenant_id)
    )
    if principal.role not in {UserRole.OWNER_DIRECTOR, UserRole.FINANCE_OPS, UserRole.COMPLIANCE}:
        permitted = []
        for schema in IMPORT_FIELDS:
            if set(principal.job_functions).intersection(WRITER_JOBS[schema]):
                permitted.append(schema)
        query = query.where(BusinessImportBatch.schema_name.in_(permitted))
    if schema_name:
        query = query.where(BusinessImportBatch.schema_name == schema_name)
    rows = db.scalars(
        query.order_by(BusinessImportBatch.created_at.desc(), BusinessImportBatch.id).limit(limit)
    )
    return ImportBatchesResponse(
        batches=[
            ImportBatchView(
                id=row.id,
                schema_name=row.schema_name,
                imported_rows=row.imported_rows,
                duplicate_rows=row.duplicate_rows,
                synthetic=row.synthetic,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )


@router.post("/{schema_name}/preview", response_model=CsvImportPreview)
def preview(
    schema_name: ImportSchema,
    request: CsvImportRequest,
    principal: CurrentUser,
    db: Session = Depends(get_db),
):
    return prepare(db, principal, schema_name, request.csv_text, request.mapping_id).preview


@router.post("/{schema_name}/commit", response_model=CsvImportResult)
def commit(
    schema_name: ImportSchema,
    request: CsvImportRequest,
    principal: AuthPrincipal = Depends(require_step_up()),
    db: Session = Depends(get_db),
):
    authorize(principal, schema_name)
    result = commit_import(db, principal, schema_name, request.csv_text, request.mapping_id)
    _after_commit(db, principal)
    return result


def _after_commit(db: Session, principal: AuthPrincipal) -> None:
    """New records may cross an alert threshold; a failed check never fails the import."""
    try:
        alerts.evaluate(db, str(principal.tenant_id), dt.date.today())
    except Exception:
        db.rollback()
