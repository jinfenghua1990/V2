from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str):
    kwargs = {"future": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if database_url.startswith("sqlite:///"):
            database_path = database_url[len("sqlite:///"):]
            if database_path and database_path != ":memory:":
                Path(database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    return create_engine(database_url, **kwargs)


DATABASE_URL = os.getenv("V2_DATABASE_URL", "sqlite:///./data/v2.db")
engine = build_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # The first slice uses metadata creation for local development. A versioned
    # migration will be added before any shared or production database is used.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
