"""Integration tests for JARVIS Real-Time WebSocket Endpoint."""

import json
import pytest
from starlette.testclient import TestClient
from app.core.config import get_settings
from app.main import create_app


def test_websocket_core_lifecycle():
    """Verify bidirectional WebSocket connection, initial handshake, and telemetry."""
    settings = get_settings()
    app = create_app(settings)
    client = TestClient(app)

    with client.websocket_connect("/api/v1/ws/core") as ws:
        # 1. Handshake greeting
        init_data = json.loads(ws.receive_text())
        assert init_data["type"] == "CORE_CONNECTED"
        assert init_data["status"] == "ONLINE"
        assert init_data["system_name"] == "J.A.R.V.I.S."

        # 2. Ping-Pong
        ws.send_text(json.dumps({"type": "PING"}))
        pong_data = json.loads(ws.receive_text())
        assert pong_data["type"] == "PONG"
        assert "timestamp" in pong_data

        # 3. Core state query
        ws.send_text(json.dumps({"type": "QUERY_CORE_STATE"}))
        state_data = json.loads(ws.receive_text())
        assert state_data["type"] == "CORE_STATE"
        assert state_data["status"] == "NOMINAL"
        assert state_data["arc_reactor_pulse"] == "STEADY"

        # 4. Waveform sample telemetry
        ws.send_text(json.dumps({"type": "AUDIO_WAVEFORM_SAMPLE", "level": 0.85}))
        wave_data = json.loads(ws.receive_text())
        assert wave_data["type"] == "WAVEFORM_ACK"
        assert wave_data["level"] == 0.85

        # 5. Invalid JSON handling
        ws.send_text("not-a-valid-json")
        err_data = json.loads(ws.receive_text())
        assert err_data["type"] == "ERROR"
