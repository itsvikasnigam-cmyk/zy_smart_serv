from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import settings


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def db_session() -> Session:
    return SessionLocal()


def db_ping() -> None:
    with engine.begin() as conn:
        conn.execute(text("SELECT 1"))

