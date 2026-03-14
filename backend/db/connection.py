"""
Database connection management using SQLAlchemy async engine.
"""

from __future__ import annotations

import logging
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

logger = logging.getLogger("voice-ai.db")

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


async def get_session() -> AsyncSession:
    """Dependency: yield a DB session."""
    async with async_session_factory() as session:
        yield session


async def init_db():
    """Create tables on startup (dev convenience)."""
    async with engine.begin() as conn:
        from db.models import Base  # noqa: F811
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ensured")


async def close_db():
    """Dispose engine on shutdown."""
    await engine.dispose()
    logger.info("Database engine disposed")
