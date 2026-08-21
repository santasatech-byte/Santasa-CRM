"""
Hospital CRM - Database Architecture
SQLAlchemy 2.0 ORM with connection pooling, declarative base, and timestamp audit mixins.
"""
from datetime import datetime, timezone
import uuid
from typing import Generator
from sqlalchemy import create_engine, DateTime, String, select, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session, Mapped, mapped_column
from app.core.config import settings
from app.core.logging import logger

import os

# Database connection options
db_url = settings.DATABASE_URL
connect_args = {}
if db_url.startswith("sqlite"):
    if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        db_url = "sqlite:////tmp/hospital_crm.db"
    connect_args = {"check_same_thread": False}

engine = create_engine(
    db_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class BaseModel(Base):
    """Abstract base model with standard fields for all Hospital CRM tables."""
    __abstract__ = True

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )


def get_db() -> Generator[Session, None, None]:
    """Dependency for providing database sessions with auto-rollback on exception."""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def check_db_health() -> bool:
    """Verifies that the database engine can successfully execute a query."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database healthcheck failed: {str(e)}")
        return False
