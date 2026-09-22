from __future__ import annotations

from typing import Optional

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from . import models  # noqa: F401
from .db import Base, SessionLocal, engine, get_db
from .master_data import resolve_party, resolve_product, resolve_source_record
from .schemas import (
    PartyResolveRequest,
    ProductResolveRequest,
    ResolveResponse,
    SourceRecordResolveRequest,
)


def create_app(
    *,
    db_engine: Optional[Engine] = None,
    session_factory: Optional[sessionmaker] = None,
    initialize: bool = True,
) -> FastAPI:
    app = FastAPI(title="V2", version="0.1.0")
    actual_engine = db_engine or engine
    actual_factory = session_factory or SessionLocal

    if initialize:
        Base.metadata.create_all(bind=actual_engine)

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

    @app.post("/api/v1/parties/resolve", response_model=ResolveResponse)
    def resolve_party_endpoint(
        body: PartyResolveRequest,
        db: Session = Depends(get_db),
    ):
        try:
            return resolve_party(db, **body.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/v1/products/resolve", response_model=ResolveResponse)
    def resolve_product_endpoint(
        body: ProductResolveRequest,
        db: Session = Depends(get_db),
    ):
        try:
            return resolve_product(db, **body.model_dump())
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
    ):
        try:
            return resolve_source_record(
                db,
                source_record_id=source_record_id,
                **body.model_dump(),
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return app


app = create_app()
