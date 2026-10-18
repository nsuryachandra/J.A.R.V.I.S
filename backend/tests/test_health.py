"""Integration tests for /healthz and /readyz endpoints."""

from unittest.mock import patch
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_healthz_endpoint(client: AsyncClient):
    """Verify liveness probe returns status 200 with app metadata."""
    response = await client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app"] == "JARVIS-TEST"
    assert data["environment"] == "testing"


@pytest.mark.asyncio
async def test_readyz_endpoint_healthy(client: AsyncClient):
    """Verify readiness probe returns 200 when database probe succeeds."""
    response = await client.get("/readyz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_readyz_endpoint_database_down(client: AsyncClient):
    """Verify readiness probe returns 503 when database is unresponsive."""
    with patch("app.api.v1.health.check_database_health", return_value=False):
        response = await client.get("/readyz")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unready"
        assert data["database"] == "disconnected"


@pytest.mark.asyncio
async def test_root_welcome_endpoint(client: AsyncClient):
    """Verify root / endpoint returns operational system status."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert data["app"] == "JARVIS-TEST"
