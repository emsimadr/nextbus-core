"""
FastAPI application for bus-tracker.

Lifespan manages httpx client, cache, and board service.
Routes: /v1/board, /v1/board/{key}, /health.
Optional API key authentication on /v1/* endpoints.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from src.board import BoardService
from src.cache import TTLCache
from src.config import AppConfig, load_config
from src.mbta_client import MBTAClient
from src.models import BoardItemResponse, BoardResponse

logger = logging.getLogger(__name__)

# Global references set during lifespan
_board_service: Optional[BoardService] = None
_config: Optional[AppConfig] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load config, create HTTP client, cache, board service."""
    global _board_service, _config

    # Configure logging
    log_level = os.environ.get("LOG_LEVEL", "info").upper()
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    _config = load_config()
    logger.info(
        "Loaded config: %d stops, cache_ttl=%d, stale_max_age=%d",
        len(_config.stops),
        _config.cache_ttl,
        _config.stale_max_age,
    )

    async with httpx.AsyncClient() as http_client:
        mbta = MBTAClient(
            http_client=http_client,
            base_url=_config.mbta_base_url,
            api_key=_config.mbta_api_key,
        )
        cache = TTLCache(
            ttl=_config.cache_ttl,
            stale_max_age=_config.stale_max_age,
        )
        _board_service = BoardService(
            config=_config, mbta_client=mbta, cache=cache
        )
        logger.info("Bus tracker ready")
        yield

    _board_service = None
    _config = None


app = FastAPI(
    title="Bus Tracker API",
    version="1.0.0",
    description="""
A realtime bus arrival tracking API that tells you when to leave your house to catch the next bus.

## Features

- **Realtime-first**: MBTA predictions with schedule fallback
- **Walk-time aware**: Computes when you need to leave, not just when the bus arrives
- **Resilient**: Serves stale cached data when MBTA is unreachable
- **Simple**: One request, small JSON response, easy to parse

## Stability

This is API version v1. All fields and endpoints are stable. See API-CONTRACT.md for versioning policy.

## Authentication

Optional API key via `X-API-Key` header. The `/health` endpoint is always unauthenticated.
    """.strip(),
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "board",
            "description": "Bus arrival data for configured stops",
        },
        {
            "name": "health",
            "description": "Service health check",
        },
    ],
    docs_url="/docs",
    redoc_url="/redoc",
)


# ---------------------------------------------------------------------------
# Authentication dependency
# ---------------------------------------------------------------------------

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(
    api_key: Optional[str] = Security(api_key_header),
) -> None:
    """Check API key if one is configured."""
    if _config is None or _config.api_key is None:
        return  # No auth configured
    if api_key != _config.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    tags=["health"],
    summary="Health check",
    response_description="Service is healthy",
)
async def health():
    """
    Health check endpoint for monitoring and Docker health checks.
    
    Always returns HTTP 200 with a simple JSON response.
    No authentication required.
    """
    return {"status": "healthy"}


@app.get(
    "/v1/board",
    response_model=BoardResponse,
    dependencies=[Depends(verify_api_key)],
    tags=["board"],
    summary="Get all stops",
    response_description="All configured stops with their next arrivals",
)
async def get_board():
    """
    Return all configured stops with their next arrivals.
    
    Returns a list of all stops defined in `config.yaml`, each with:
    - Next arrival time and walk-time-aware leave time
    - Up to 2 alternative arrivals
    - Status indicator (ok, stale, no_service, error)
    
    This endpoint is useful for Home Assistant or dashboards showing multiple routes.
    For single-stop displays (ESP32, etc.), use `/v1/board/{key}` instead.
    """
    if _board_service is None:
        raise HTTPException(status_code=503, detail="Service not ready")
    return await _board_service.get_board()


@app.get(
    "/v1/board/{key}",
    response_model=BoardItemResponse,
    dependencies=[Depends(verify_api_key)],
    tags=["board"],
    summary="Get single stop",
    response_description="One stop with its next arrival",
    responses={
        200: {
            "description": "Stop found with arrival data",
        },
        404: {
            "description": "Stop key not found in configuration",
            "content": {
                "application/json": {
                    "example": {"detail": "Board item 'unknown_key' not found"}
                }
            },
        },
    },
)
async def get_board_item(key: str):
    """
    Return a single configured stop by its config key.
    
    The `key` must match one of the stop keys defined in `config.yaml`.
    
    Returns:
    - Next arrival with walk-time-aware leave time
    - Up to 2 alternative arrivals
    - Status indicator (ok, stale, no_service, error)
    
    This endpoint is recommended for:
    - ESP32 e-ink displays (single stop view)
    - Dedicated per-route dashboards
    - Any client that only cares about one specific route/stop
    
    Example keys: `route_1_inbound`, `route_73_outbound`
    """
    if _board_service is None:
        raise HTTPException(status_code=503, detail="Service not ready")
    item = await _board_service.get_board_item(key)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Board item '{key}' not found")
    return item
