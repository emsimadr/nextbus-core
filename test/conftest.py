"""
Shared test fixtures for bus-tracker.

Provides:
- MBTA fixture data loaders
- Fake MBTA server for E2E tests
- Bus-tracker server for E2E tests
- Temporary config files
"""

import json
import os
import tempfile
import time
from pathlib import Path
from threading import Thread

import httpx
import pytest
import uvicorn
from pytest_httpserver import HTTPServer

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "mbta"


# ---------------------------------------------------------------------------
# Fixture data loaders
# ---------------------------------------------------------------------------

def load_fixture(name: str) -> dict:
    """Load a JSON fixture from test/fixtures/mbta/."""
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# E2E fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fake_mbta_server():
    """
    A real HTTP server that impersonates the MBTA v3 API.

    Serves fixture JSON responses. Tests configure what the server returns
    by setting handler functions on the server before making requests.

    Uses pytest-httpserver to handle real HTTP requests.
    """
    server = HTTPServer(host="127.0.0.1")
    server.expect_request("/predictions").respond_with_json({"data": []})
    server.expect_request("/schedules").respond_with_json({"data": []})
    server.start()
    yield server
    server.clear()
    if server.is_running():
        server.stop()


@pytest.fixture()
def config_file(fake_mbta_server, tmp_path):
    """
    Write a temporary config.yaml that points at the fake MBTA server.
    Returns the path to the config file.
    """
    mbta_url = f"http://{fake_mbta_server.host}:{fake_mbta_server.port}"
    config_content = f"""\
mbta_base_url: "{mbta_url}"
cache_ttl: 20
stale_max_age: 300

stops:
  - key: "test_route"
    label: "Test Route - Inbound"
    route_id: "1"
    stop_id: "place-test"
    direction_id: 0
    walk_minutes: 5
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(config_content)
    return str(config_path)


@pytest.fixture()
def bus_tracker_url(config_file):
    """
    Start the actual bus-tracker FastAPI app on a random port.
    Yields the base URL (e.g. http://127.0.0.1:9123).
    Shuts down after the test.
    """
    # Import here to avoid import errors if src is not yet built.
    # This fixture will be usable once the app module exists.
    os.environ["CONFIG_PATH"] = config_file
    os.environ["MBTA_API_KEY"] = "test-key"
    os.environ["PORT"] = "0"  # Let uvicorn pick a random port

    try:
        from src.app import app
    except ImportError:
        pytest.skip("src.app not yet implemented")

    # Use a simple approach: run uvicorn in a thread on a known port.
    # For a more robust approach, use a subprocess.
    import socket

    # Find a free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to start
    base_url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            httpx.get(f"{base_url}/health", timeout=0.5)
            break
        except httpx.ConnectError:
            time.sleep(0.1)
    else:
        pytest.fail("Bus tracker server did not start in time")

    yield base_url

    server.should_exit = True
    thread.join(timeout=5)
