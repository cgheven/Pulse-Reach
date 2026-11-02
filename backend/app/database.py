from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()

# The database is remote (Neon), so every round trip is expensive. Keep connections open and reuse them:
# - no pool_pre_ping (it costs an extra round trip on every request); stale connections are recycled instead
# - TCP keepalives stop idle connections being dropped by NATs / the pooler
# - no per-connection setup queries: every model is schema-qualified, so search_path isn't needed
engine = create_engine(
    settings.sqlalchemy_url,
    pool_pre_ping=False,
    pool_recycle=240,
    pool_size=10,
    max_overflow=10,
    pool_use_lifo=True,
    connect_args={
        "connect_timeout": 15,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    },
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    schema = get_settings().db_schema
    with engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def warm_pool(size: int = 4) -> None:
    """Open a few connections up front so the first page loads don't each pay the slow TLS + auth handshake."""
    from concurrent.futures import ThreadPoolExecutor

    def touch(_: int) -> None:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    with ThreadPoolExecutor(max_workers=size) as pool:
        list(pool.map(touch, range(size)))
