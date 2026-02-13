"""Tests for FastAPI endpoints (TestClient with mocked BoardService)."""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.models import (
    Arrival,
    ArrivalSource,
    BoardItemResponse,
    BoardResponse,
    ErrorCode,
    ErrorDetail,
    Status,
)


NOW = datetime.now(timezone.utc)


def _make_arrival(minutes=8):
    return Arrival(
        time=NOW + timedelta(minutes=minutes),
        minutes=minutes,
        leave_in_minutes=minutes - 4,
        source=ArrivalSource.realtime,
        trip_id="trip-1",
    )


def _make_board_item(key="test_route", status=Status.ok, arrival=None, alternatives=None):
    return BoardItemResponse(
        key=key,
        label="Test Route",
        route_id="77",
        stop_id="2261",
        direction_id=1,
        walk_minutes=4,
        status=status,
        arrival=arrival or (None if status != Status.ok else _make_arrival()),
        alternatives=alternatives or [],
    )


def _make_board_response(items=None):
    return BoardResponse(
        as_of=NOW,
        items=items or [_make_board_item()],
    )


@pytest.fixture()
def mock_board_service():
    """Create a mocked board service and patch it into the app module."""
    mock = AsyncMock()
    mock.get_board.return_value = _make_board_response()
    mock.get_board_item.return_value = _make_board_item()
    return mock


@pytest.fixture()
def client(mock_board_service):
    """TestClient with mocked board service and no auth."""
    import src.app as app_module

    # Patch lifespan to skip real startup
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    original_lifespan = app_module.app.router.lifespan_context
    app_module.app.router.lifespan_context = noop_lifespan
    app_module._board_service = mock_board_service
    app_module._config = type("C", (), {"api_key": None})()
    with TestClient(app_module.app, raise_server_exceptions=False) as c:
        yield c
    app_module._board_service = None
    app_module._config = None
    app_module.app.router.lifespan_context = original_lifespan


@pytest.fixture()
def auth_client(mock_board_service):
    """TestClient with mocked board service and API key auth enabled."""
    import src.app as app_module

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    original_lifespan = app_module.app.router.lifespan_context
    app_module.app.router.lifespan_context = noop_lifespan
    app_module._board_service = mock_board_service
    app_module._config = type("C", (), {"api_key": "test-secret"})()
    with TestClient(app_module.app, raise_server_exceptions=False) as c:
        yield c
    app_module._board_service = None
    app_module._config = None
    app_module.app.router.lifespan_context = original_lifespan


class TestHealthEndpoint:
    def test_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}

    def test_no_auth_needed(self, auth_client):
        resp = auth_client.get("/health")
        assert resp.status_code == 200


class TestBoardEndpoint:
    def test_returns_board(self, client):
        resp = client.get("/v1/board")
        assert resp.status_code == 200
        data = resp.json()
        assert "as_of" in data
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["key"] == "test_route"
        assert item["status"] == "ok"
        assert item["arrival"] is not None
        assert item["arrival"]["source"] == "realtime"

    def test_response_has_correct_schema(self, client):
        resp = client.get("/v1/board")
        data = resp.json()
        item = data["items"][0]
        assert "label" in item
        assert "route_id" in item
        assert "walk_minutes" in item
        assert "alternatives" in item
        assert isinstance(item["alternatives"], list)


class TestBoardItemEndpoint:
    def test_returns_item(self, client):
        resp = client.get("/v1/board/test_route")
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "test_route"
        assert data["status"] == "ok"

    def test_not_found(self, client, mock_board_service):
        mock_board_service.get_board_item.return_value = None
        resp = client.get("/v1/board/nonexistent")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


class TestAuthentication:
    def test_rejects_without_key(self, auth_client):
        resp = auth_client.get("/v1/board")
        assert resp.status_code == 401

    def test_rejects_wrong_key(self, auth_client):
        resp = auth_client.get("/v1/board", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401

    def test_accepts_correct_key(self, auth_client):
        resp = auth_client.get("/v1/board", headers={"X-API-Key": "test-secret"})
        assert resp.status_code == 200

    def test_board_item_requires_key(self, auth_client):
        resp = auth_client.get("/v1/board/test_route")
        assert resp.status_code == 401

    def test_board_item_accepts_key(self, auth_client):
        resp = auth_client.get(
            "/v1/board/test_route", headers={"X-API-Key": "test-secret"}
        )
        assert resp.status_code == 200

    def test_health_no_auth_needed(self, auth_client):
        resp = auth_client.get("/health")
        assert resp.status_code == 200
