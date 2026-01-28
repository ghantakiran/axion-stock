"""Database engine and session factories for async and sync access."""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker

from src.settings import get_settings

_async_engine = None
_sync_engine = None


def get_async_engine():
    """Get or create the async database engine."""
    global _async_engine
    if _async_engine is None:
        settings = get_settings()
        _async_engine = create_async_engine(
            settings.database_url,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _async_engine


def get_sync_engine():
    """Get or create the sync database engine (for backward compatibility)."""
    global _sync_engine
    if _sync_engine is None:
        settings = get_settings()
        _sync_engine = create_engine(
            settings.database_sync_url,
            pool_pre_ping=True,
        )
    return _sync_engine


def get_async_session_factory():
    return async_sessionmaker(bind=get_async_engine(), expire_on_commit=False)


def get_sync_session_factory():
    return sessionmaker(bind=get_sync_engine())


# Convenience aliases
AsyncSessionLocal = get_async_session_factory
SyncSessionLocal = get_sync_session_factory
