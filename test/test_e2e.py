"""
End-to-end tests: real HTTP servers, real bus-tracker app, fake MBTA.

Each test uses real httpx calls against running servers.
Nothing is mocked in-process.
"""

import os
import socket
import time
from datetime import datetime, timezone, timedelta
from threading import Thread

import httpx
import pytest
import uvicorn
from pytest_httpserver import HTTPServer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _future_iso(minutes: int = 10) -> str:
    t = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    return t.isoformat()


def _mbta_predictions(*arrivals_minutes, trip_prefix="trip"):
    data = []
    for i, mins in enumerate(arrivals_minutes):
        data.append({
            "attributes": {
                "arrival_time": _future_iso(mins),
                "departure_time": None,
            },
            "relationships": {
                "trip": {"data": {"id": f"{trip_prefix}-{i+1}"}},
                "route": {"data": {"id": "1"}},
                "stop": {"data": {"id": "place-test"}},
            },
        })
    return {"data": data}


EMPTY_RESPONSE = {"data": []}


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_bus_tracker(config_path: str, env_overrides: dict = None):
    """
    Start a bus-tracker server by setting globals on the app module directly.
    Returns (base_url, uvicorn_server, thread).
    """
    env = env_overrides or {}
    os.environ["CONFIG_PATH"] = config_path
    for k, v in env.items():
        os.environ[k] = v

    # Import and build components manually
    from src.config import load_config
    from src.cache import TTLCache
    from src.mbta_client import MBTAClient
    from src.board import BoardService
    import src.app as app_module

    config = load_config(config_path)

    # We need a running httpx client. Create one that won't be closed
    # until the server shuts down.
    import httpx as httpx_mod

    http_client = httpx_mod.AsyncClient()
    mbta = MBTAClient(
        http_client=http_client,
        base_url=config.mbta_base_url,
        api_key=config.mbta_api_key,
    )
    cache = TTLCache(ttl=config.cache_ttl, stale_max_age=config.stale_max_age)
    board_service = BoardService(config=config, mbta_client=mbta, cache=cache)

    # Set globals directly -- skip lifespan
    app_module._config = config
    app_module._board_service = board_service

    port = _find_free_port()

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def noop_lifespan(app):
        yield
        await http_client.aclose()

    app_module.app.router.lifespan_context = noop_lifespan

    uvi_config = uvicorn.Config(
        app_module.app, host="127.0.0.1", port=port, log_level="warning"
    )
    server = uvicorn.Server(uvi_config)
    thread = Thread(target=server.run, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            httpx.get(f"{base_url}/health", timeout=1.0)
            break
        except (httpx.ConnectError, httpx.ReadError, httpx.ConnectTimeout):
            time.sleep(0.1)
    else:
        pytest.fail("Bus tracker server did not start")

    return base_url, server, thread, app_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fake_mbta():
    server = HTTPServer(host="127.0.0.1")
    server.expect_request("/predictions").respond_with_json(EMPTY_RESPONSE)
    server.expect_request("/schedules").respond_with_json(EMPTY_RESPONSE)
    server.start()
    yield server
    server.clear()
    if server.is_running():
        server.stop()


@pytest.fixture(scope="module")
def bus_tracker(fake_mbta, tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("e2e")
    mbta_url = f"http://{fake_mbta.host}:{fake_mbta.port}"
    config_content = f"""\
mbta_base_url: "{mbta_url}"
cache_ttl: 2
stale_max_age: 60

stops:
  - key: "test_route"
    label: "Test Route"
    route_id: "1"
    stop_id: "place-test"
    direction_id: 0
    walk_minutes: 5
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content)

    base_url, server, thread, app_mod = _start_bus_tracker(
        str(config_path), {"MBTA_API_KEY": "test-key"}
    )
    os.environ.pop("API_KEY", None)

    yield base_url, fake_mbta

    server.should_exit = True
    thread.join(timeout=5)
    app_mod._board_service = None
    app_mod._config = None


# ---------------------------------------------------------------------------
# E2E Tests
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestE2E:

    def test_health(self, bus_tracker):
        base_url, _ = bus_tracker
        resp = httpx.get(f"{base_url}/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}

    def test_happy_path_realtime(self, bus_tracker):
        base_url, fake_mbta = bus_tracker
        fake_mbta.clear()
        fake_mbta.expect_request("/predictions").respond_with_json(
            _mbta_predictions(8, 20, 35)
        )
        fake_mbta.expect_request("/schedules").respond_with_json(EMPTY_RESPONSE)

        # Wait for cache to expire
        time.sleep(2.5)

        resp = httpx.get(f"{base_url}/v1/board")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["status"] == "ok"
        assert item["arrival"] is not None
        assert item["arrival"]["source"] == "realtime"
        assert item["arrival"]["minutes"] >= 7
        assert item["arrival"]["leave_in_minutes"] == item["arrival"]["minutes"] - 5
        assert len(item["alternatives"]) == 2

    def test_schedule_fallback(self, bus_tracker):
        base_url, fake_mbta = bus_tracker
        fake_mbta.clear()
        fake_mbta.expect_request("/predictions").respond_with_json(EMPTY_RESPONSE)
        fake_mbta.expect_request("/schedules").respond_with_json(
            _mbta_predictions(15, trip_prefix="sched")
        )

        time.sleep(2.5)
        resp = httpx.get(f"{base_url}/v1/board")
        item = resp.json()["items"][0]
        assert item["status"] == "ok"
        assert item["arrival"]["source"] == "schedule"

    def test_no_service(self, bus_tracker):
        base_url, fake_mbta = bus_tracker
        fake_mbta.clear()
        fake_mbta.expect_request("/predictions").respond_with_json(EMPTY_RESPONSE)
        fake_mbta.expect_request("/schedules").respond_with_json(EMPTY_RESPONSE)

        time.sleep(2.5)
        resp = httpx.get(f"{base_url}/v1/board")
        item = resp.json()["items"][0]
        assert item["status"] == "no_service"
        assert item["arrival"] is None
        assert item["alternatives"] == []

    def test_stale_cache(self, bus_tracker):
        base_url, fake_mbta = bus_tracker
        fake_mbta.clear()
        fake_mbta.expect_request("/predictions").respond_with_json(
            _mbta_predictions(30)
        )
        fake_mbta.expect_request("/schedules").respond_with_json(EMPTY_RESPONSE)

        time.sleep(2.5)
        resp1 = httpx.get(f"{base_url}/v1/board")
        assert resp1.json()["items"][0]["status"] == "ok"

        # Wait for cache TTL to expire
        time.sleep(3)

        # MBTA returns 500
        fake_mbta.clear()
        fake_mbta.expect_request("/predictions").respond_with_json(
            {"errors": [{"status": "500"}]}, status=500
        )

        resp2 = httpx.get(f"{base_url}/v1/board")
        item = resp2.json()["items"][0]
        assert item["status"] == "stale"
        assert item["arrival"] is not None
        assert item["stale_as_of"] is not None

    def test_cold_start_error(self, bus_tracker):
        """After clearing cache + MBTA down, next request is an error."""
        base_url, fake_mbta = bus_tracker
        fake_mbta.clear()
        fake_mbta.expect_request("/predictions").respond_with_json(
            {"errors": [{"status": "500"}]}, status=500
        )

        # Need to clear the cache in the running service
        # Wait for stale_max_age to expire is too long.
        # Instead, access the board service's cache directly.
        import src.app as app_module
        app_module._board_service._cache.clear()

        time.sleep(2.5)
        resp = httpx.get(f"{base_url}/v1/board")
        item = resp.json()["items"][0]
        assert item["status"] == "error"
        assert item["error"]["code"] == "mbta_unreachable"

    def test_board_key_lookup(self, bus_tracker):
        base_url, fake_mbta = bus_tracker
        fake_mbta.clear()
        fake_mbta.expect_request("/predictions").respond_with_json(
            _mbta_predictions(10)
        )
        fake_mbta.expect_request("/schedules").respond_with_json(EMPTY_RESPONSE)

        import src.app as app_module
        app_module._board_service._cache.clear()

        resp = httpx.get(f"{base_url}/v1/board/test_route")
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"] == "test_route"
        assert data["status"] == "ok"

    def test_board_key_not_found(self, bus_tracker):
        base_url, _ = bus_tracker
        resp = httpx.get(f"{base_url}/v1/board/nonexistent")
        assert resp.status_code == 404

    def test_walk_time_computation(self, bus_tracker):
        base_url, fake_mbta = bus_tracker
        fake_mbta.clear()
        fake_mbta.expect_request("/predictions").respond_with_json(
            _mbta_predictions(8)
        )
        fake_mbta.expect_request("/schedules").respond_with_json(EMPTY_RESPONSE)

        import src.app as app_module
        app_module._board_service._cache.clear()

        resp = httpx.get(f"{base_url}/v1/board")
        item = resp.json()["items"][0]
        arrival = item["arrival"]
        assert arrival["minutes"] >= 7
        assert arrival["leave_in_minutes"] == arrival["minutes"] - 5


@pytest.mark.e2e
class TestE2EAuth:
    def test_api_key_enforcement(self, fake_mbta, tmp_path_factory):
        tmp_path = tmp_path_factory.mktemp("e2e_auth")
        mbta_url = f"http://{fake_mbta.host}:{fake_mbta.port}"
        config_content = f"""\
mbta_base_url: "{mbta_url}"
cache_ttl: 2
stale_max_age: 60
stops:
  - key: "test"
    label: "Test"
    route_id: "1"
    stop_id: "place-test"
    direction_id: 0
    walk_minutes: 0
"""
        config_path = tmp_path / "config_auth.yaml"
        config_path.write_text(config_content)

        base_url, server, thread, app_mod = _start_bus_tracker(
            str(config_path),
            {"MBTA_API_KEY": "test-key", "API_KEY": "my-secret"},
        )

        try:
            # No key -> 401
            resp = httpx.get(f"{base_url}/v1/board")
            assert resp.status_code == 401

            # Wrong key -> 401
            resp = httpx.get(f"{base_url}/v1/board", headers={"X-API-Key": "wrong"})
            assert resp.status_code == 401

            # Correct key -> 200
            fake_mbta.clear()
            fake_mbta.expect_request("/predictions").respond_with_json(EMPTY_RESPONSE)
            fake_mbta.expect_request("/schedules").respond_with_json(EMPTY_RESPONSE)
            resp = httpx.get(
                f"{base_url}/v1/board", headers={"X-API-Key": "my-secret"}
            )
            assert resp.status_code == 200

            # Health -> 200 without key
            resp = httpx.get(f"{base_url}/health")
            assert resp.status_code == 200
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            app_mod._board_service = None
            app_mod._config = None
            os.environ.pop("API_KEY", None)
