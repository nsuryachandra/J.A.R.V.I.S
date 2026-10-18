"""Health and readiness endpoints for cloud orchestrators (Render/K8s)."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from app.core.config import Settings, get_settings
from app.core.database import check_database_health

router = APIRouter()


class LivenessResponse(BaseModel):
    status: str
    app: str
    environment: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    timestamp: str


@router.get("/healthz", response_model=LivenessResponse, summary="Liveness Probe")
async def healthz(settings: Settings = Depends(get_settings)) -> LivenessResponse:
    """Liveness probe to confirm the HTTP process is responsive."""
    return LivenessResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
    )


@router.get(
    "/readyz",
    response_model=ReadinessResponse,
    summary="Readiness Probe",
    responses={
        200: {"description": "Service and database are fully operational"},
        503: {"description": "Database probe failed, service not ready for traffic"},
    },
)
async def readyz(response: Response) -> ReadinessResponse:
    """Readiness probe verifying persistent database connectivity."""
    is_healthy = await check_database_health()
    iso_now = datetime.now(timezone.utc).isoformat()

    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="unready",
            database="disconnected",
            timestamp=iso_now,
        )

    return ReadinessResponse(
        status="ready",
        database="connected",
        timestamp=iso_now,
    )
