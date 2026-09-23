from __future__ import annotations

from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session, sessionmaker

from .db import SessionLocal, get_db
from .master_data import (
    get_party,
    get_product,
    list_audit_events,
    list_review_source_records,
    resolve_party,
    resolve_product,
    resolve_source_record,
)
from .schemas import (
    PartyResolveRequest,
    PartyResponse,
    ProductResolveRequest,
    ProductResponse,
    AuditEventResponse,
    ResolveResponse,
    SourceRecordResolveRequest,
    SourceRecordReviewResponse,
)
from .security import (
    Principal,
    allow_local_access,
    require_api_access,
    require_write_access,
)


def create_app(
    *,
    session_factory: Optional[sessionmaker] = None,
    enforce_auth: bool = True,
) -> FastAPI:
    app = FastAPI(title="V2", version="0.1.0")
    actual_factory = session_factory or SessionLocal
    read_dependency = require_api_access if enforce_auth else allow_local_access
    write_dependency = require_write_access if enforce_auth else allow_local_access

    def override_get_db():
        db = actual_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "service": "v2", "dataModel": "canonical-master-v1"}

    @app.get("/api/v1/parties/{party_id}", response_model=PartyResponse)
    def get_party_endpoint(
        party_id: str,
        db: Session = Depends(get_db),
        _principal: Principal = Depends(read_dependency),
    ):
        try:
            return get_party(db, party_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/v1/products/{product_id}", response_model=ProductResponse)
    def get_product_endpoint(
        product_id: str,
        db: Session = Depends(get_db),
        _principal: Principal = Depends(read_dependency),
    ):
        try:
            return get_product(db, product_id)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/v1/source-records/review",
        response_model=List[SourceRecordReviewResponse],
    )
    def list_review_source_records_endpoint(
        limit: int = Query(default=100, ge=1, le=200),
        db: Session = Depends(get_db),
        _principal: Principal = Depends(read_dependency),
    ):
        return list_review_source_records(db, limit=limit)

    @app.get("/api/v1/audit-events", response_model=List[AuditEventResponse])
    def list_audit_events_endpoint(
        entity_type: Optional[str] = Query(default=None, min_length=1, max_length=24),
        entity_id: Optional[str] = Query(default=None, min_length=1, max_length=36),
        source_record_id: Optional[str] = Query(default=None, min_length=1, max_length=36),
        limit: int = Query(default=100, ge=1, le=200),
        db: Session = Depends(get_db),
        _principal: Principal = Depends(read_dependency),
    ):
        return list_audit_events(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            source_record_id=source_record_id,
            limit=limit,
        )

    @app.post("/api/v1/parties/resolve", response_model=ResolveResponse)
    def resolve_party_endpoint(
        body: PartyResolveRequest,
        db: Session = Depends(get_db),
        principal: Principal = Depends(write_dependency),
    ):
        try:
            return resolve_party(
                db,
                **body.model_dump(),
                actor_type=principal.actor_type,
                actor_id=principal.actor_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/products/resolve", response_model=ResolveResponse)
    def resolve_product_endpoint(
        body: ProductResolveRequest,
        db: Session = Depends(get_db),
        principal: Principal = Depends(write_dependency),
    ):
        try:
            return resolve_product(
                db,
                **body.model_dump(),
                actor_type=principal.actor_type,
                actor_id=principal.actor_id,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/v1/source-records/{source_record_id}/resolve",
        response_model=ResolveResponse,
    )
    def resolve_source_record_endpoint(
        source_record_id: str,
        body: SourceRecordResolveRequest,
        db: Session = Depends(get_db),
        principal: Principal = Depends(write_dependency),
    ):
        try:
            return resolve_source_record(
                db,
                source_record_id=source_record_id,
                **body.model_dump(),
                actor_type=principal.actor_type,
                actor_id=principal.actor_id,
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app


app = create_app()
