"""FastAPI application factory, lifespan management, CORS, and routing."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import api_v1_router
from app.api.v1.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.database import close_db, get_engine
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.models.base import Base

logger = logging.getLogger("jarvis.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycle."""
    settings: Settings = app.state.settings
    logger.info(
        f"Starting {settings.app_name} in {settings.environment} mode",
        extra={"timezone": settings.timezone, "environment": settings.environment},
    )

    # In local SQLite development or testing mode, automatically create tables if needed
    if settings.is_sqlite:
        engine = get_engine(settings)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Verified SQLite tables are created.")

    yield

    logger.info(f"Shutting down {settings.app_name}...")
    await close_db()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure a production-ready FastAPI application instance."""
    app_settings = settings or get_settings()

    # Configure structured logging
    setup_logging(
        log_level=app_settings.log_level,
        json_output=app_settings.is_production,
    )

    app = FastAPI(
        title=app_settings.app_name,
        description="JARVIS — Personal AI Operating System Core Gateway",
        version="0.1.0",
        docs_url="/docs" if not app_settings.is_production else None,
        redoc_url="/redoc" if not app_settings.is_production else None,
        lifespan=lifespan,
    )

    # Attach settings to application state
    app.state.settings = app_settings

    # Configure CORS middleware
    origins = (
        app_settings.allowed_origins
        if isinstance(app_settings.allowed_origins, list)
        else [app_settings.allowed_origins]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register standardized exception handlers
    register_exception_handlers(app)

    # Mount top-level health routes for cloud health checks (Render /healthz and /readyz)
    app.include_router(health_router)

    # Mount API v1 router
    app.include_router(api_v1_router)

    @app.get("/", summary="Root Welcome")
    async def root(settings: Settings = Depends(get_settings)):
        return {
            "app": settings.app_name,
            "version": "0.1.0",
            "status": "operational",
            "environment": settings.environment,
            "timezone": settings.timezone,
        }

    return app


# Default app instance for ASGI servers (uvicorn app.main:app)
app = create_app()
