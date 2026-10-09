"""Persistent header mappings, scoped to the verified tenant."""

from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.principal import AuthPrincipal
from app.contracts.customization import (
    ImportMapping,
    ImportMappingRequest,
    header_fingerprint,
    normalize_header,
)
from app.models import ImportMappingRecord
from app.services.identity import audit, tenant_lock


def view(row: ImportMappingRecord) -> ImportMapping:
    return ImportMapping.model_validate(
        {
            "id": row.id,
            "schema_name": row.schema_name,
            "name": row.name,
            "column_map": row.column_map,
            "header_fingerprint": row.header_fingerprint,
        }
    )


def list_mappings(db: Session, principal: AuthPrincipal) -> list[ImportMapping]:
    return [
        view(row)
        for row in db.scalars(
            select(ImportMappingRecord)
            .where(ImportMappingRecord.tenant_id == str(principal.tenant_id))
            .order_by(ImportMappingRecord.created_at, ImportMappingRecord.id)
        )
    ]


def match(db: Session, tenant_id: str, schema: str, headers: list[str], mapping_id=None):
    query = select(ImportMappingRecord).where(
        ImportMappingRecord.tenant_id == tenant_id,
        ImportMappingRecord.schema_name == schema,
        ImportMappingRecord.header_fingerprint == header_fingerprint(headers),
    )
    if mapping_id is not None:
        query = query.where(ImportMappingRecord.id == mapping_id)
    return db.scalar(query)


def save(db: Session, principal: AuthPrincipal, request: ImportMappingRequest, *, commit=True):
    tenant_id = str(principal.tenant_id)
    tenant_lock(db, tenant_id)
    existing = match(db, tenant_id, request.schema_name, request.headers)
    canonical = {normalize_header(k): v for k, v in request.column_map.items()}
    if existing:
        if {normalize_header(k): v for k, v in existing.column_map.items()} != canonical:
            raise HTTPException(409, "mapping_already_exists_with_different_targets")
        return view(existing)
    row = ImportMappingRecord(
        id=f"map_{uuid4().hex}",
        tenant_id=tenant_id,
        schema_name=request.schema_name,
        name=request.name,
        column_map=request.column_map,
        header_fingerprint=header_fingerprint(request.headers),
        created_by=str(principal.user_id),
    )
    db.add(row)
    db.flush()
    audit(
        db,
        principal,
        "import.mapping_created",
        "import_mapping",
        row.id,
        schema=request.schema_name,
        fingerprint=row.header_fingerprint,
    )
    if commit:
        db.commit()
    return view(row)
