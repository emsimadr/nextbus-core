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


app = FastAPI(title="Bus Tracker", lifespan=lifespan)


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


@app.get("/health")
async def health():
    """Health check endpoint. Always returns 200, no auth."""
    return {"status": "healthy"}


@app.get("/v1/board", response_model=BoardResponse, dependencies=[Depends(verify_api_key)])
async def get_board():
    """Return all configured stops with their next arrivals."""
    if _board_service is None:
        raise HTTPException(status_code=503, detail="Service not ready")
    return await _board_service.get_board()


@app.get("/v1/board/{key}", response_model=BoardItemResponse, dependencies=[Depends(verify_api_key)])
async def get_board_item(key: str):
    """Return a single configured stop by its config key."""
    if _board_service is None:
        raise HTTPException(status_code=503, detail="Service not ready")
    item = await _board_service.get_board_item(key)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Board item '{key}' not found")
    return item
