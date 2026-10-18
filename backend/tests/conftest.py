"""Pytest fixtures for async database testing, settings overrides, and HTTP test client."""

import asyncio
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool
from app.core.config import Settings, get_settings
from app.core.database import get_db_session
from app.main import create_app
from app.models.base import Base


@pytest.fixture(scope="session")
def event_loop():
    """Ensure a consistent event loop for pytest-asyncio."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Provide isolated test settings with in-memory SQLite database."""
    return Settings(
        app_name="JARVIS-TEST",
        environment="testing",
        log_level="DEBUG",
        database_url="sqlite+aiosqlite://",  # In-memory SQLite
        app_secret_key="test-secret-key-at-least-32-chars-long-for-testing",
        timezone="Asia/Kolkata",
    )


@pytest_asyncio.fixture(scope="session")
async def test_engine(test_settings: Settings) -> AsyncGenerator[AsyncEngine, None]:
    """Create in-memory SQLite engine using StaticPool for shared memory across connections."""
    engine = create_async_engine(
        test_settings.database_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated database session rolled back after every test."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(
    test_settings: Settings, test_engine: AsyncEngine, db_session: AsyncSession
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an asynchronous HTTP client with database dependency override."""
    app = create_app(test_settings)

    async def override_get_db_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_settings] = lambda: test_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
