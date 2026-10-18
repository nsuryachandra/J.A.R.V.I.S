"""Database engine, async session factory, connection pooling, and health checks."""

import logging
from typing import AsyncGenerator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.core.config import Settings, get_settings
from app.core.exceptions import DatabaseConnectionError

logger = logging.getLogger("jarvis.database")

# Global engine and session factory references
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    """Create or return the cached asynchronous database engine."""
    global _engine
    if _engine is None:
        cfg = settings or get_settings()
        engine_kwargs = {"echo": False, "future": True}

        if cfg.is_sqlite:
            # SQLite-specific connection parameters
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            # PostgreSQL connection pool settings
            engine_kwargs.update(
                {
                    "pool_size": cfg.database_pool_size,
                    "max_overflow": cfg.database_max_overflow,
                    "pool_pre_ping": True,
                }
            )

        _engine = create_async_engine(cfg.database_url, **engine_kwargs)
        logger.info(
            "Initialized async database engine",
            extra={"database_type": "sqlite" if cfg.is_sqlite else "postgresql"},
        )
    return _engine


def get_session_factory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    """Create or return the cached async session factory."""
    global _session_factory
    if _session_factory is None:
        eng = engine or get_engine()
        _session_factory = async_sessionmaker(
            bind=eng,
            class_=AsyncSession,
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for yielding transactional async database sessions."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_database_health(engine: AsyncEngine | None = None) -> bool:
    """Execute a lightweight probe ('SELECT 1') to verify database responsiveness."""
    eng = engine or get_engine()
    try:
        async with eng.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            val = result.scalar()
            return val == 1
    except Exception as exc:
        logger.error(f"Database health probe failed: {exc}")
        return False


async def close_db() -> None:
    """Cleanly dispose of the database connection pool on application shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Disposed database connection pool.")
