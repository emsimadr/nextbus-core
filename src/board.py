"""
Board service: orchestrates MBTA client, cache, and selection logic.

For each configured stop, fetches predictions (or schedules as fallback),
runs selection, and returns a BoardItemResponse.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from src.cache import TTLCache
from src.config import AppConfig, BoardItemConfig
from src.mbta_client import MBTAClient, MBTAError
from src.models import (
    Arrival,
    ArrivalSource,
    BoardItemResponse,
    BoardResponse,
    ErrorCode,
    ErrorDetail,
    Status,
)
from src.selection import select_arrivals

logger = logging.getLogger(__name__)


class BoardService:
    """
    Main service class. Produces BoardResponse from configured stops.

    Cache stores raw MBTA candidate lists so stale mode can re-filter
    and recompute minutes against current time.
    """

    def __init__(
        self, config: AppConfig, mbta_client: MBTAClient, cache: TTLCache
    ) -> None:
        self._config = config
        self._mbta = mbta_client
        self._cache = cache

    async def get_board(self) -> BoardResponse:
        """Fetch all configured stops and return a BoardResponse."""
        now = datetime.now(timezone.utc)
        items = []
        for stop_config in self._config.stops:
            item = await self._get_item(stop_config, now)
            items.append(item)
        return BoardResponse(as_of=now, items=items)

    async def get_board_item(self, key: str) -> Optional[BoardItemResponse]:
        """Fetch a single configured stop by key. Returns None if key not found."""
        stop_config = self._config.get_stop(key)
        if stop_config is None:
            return None
        now = datetime.now(timezone.utc)
        return await self._get_item(stop_config, now)

    async def _get_item(
        self, stop: BoardItemConfig, now: datetime
    ) -> BoardItemResponse:
        """Process a single board item: cache check, fetch, select."""
        base = {
            "key": stop.key,
            "label": stop.label,
            "route_id": stop.route_id,
            "stop_id": stop.stop_id,
            "direction_id": stop.direction_id,
            "walk_minutes": stop.walk_minutes,
        }

        # 1. Check fresh cache
        cached = self._cache.get(stop.key)
        if cached is not None:
            return self._build_from_candidates(
                cached.value["candidates"],
                cached.value["source"],
                stop.walk_minutes,
                now,
                base,
            )

        # 2. Fetch from MBTA
        try:
            candidates, source = await self._fetch_candidates(stop)
        except MBTAError as exc:
            logger.warning(
                "MBTA error for %s: %s", stop.key, exc
            )
            return self._handle_mbta_error(exc, stop, now, base)

        # 3. Cache the raw candidates
        self._cache.set(stop.key, {"candidates": candidates, "source": source})

        # 4. Select and build response
        return self._build_from_candidates(
            candidates, source, stop.walk_minutes, now, base
        )

    async def _fetch_candidates(
        self, stop: BoardItemConfig
    ) -> tuple[list[dict], ArrivalSource]:
        """
        Fetch candidates with realtime-first policy.

        1. Try predictions. If they yield future arrivals, use them.
        2. Otherwise, try schedules.
        3. Return (candidates, source).
        """
        predictions = await self._mbta.fetch_predictions(
            stop.route_id, stop.stop_id, stop.direction_id
        )
        if predictions:
            return predictions, ArrivalSource.realtime

        schedules = await self._mbta.fetch_schedules(
            stop.route_id, stop.stop_id, stop.direction_id
        )
        return schedules, ArrivalSource.schedule

    def _build_from_candidates(
        self,
        candidates: list[dict],
        source: ArrivalSource,
        walk_minutes: int,
        now: datetime,
        base: dict,
    ) -> BoardItemResponse:
        """Run selection on candidates and build a BoardItemResponse."""
        next_arrival, alternatives = select_arrivals(
            candidates, now, walk_minutes, source
        )

        if next_arrival is None:
            return BoardItemResponse(
                **base, status=Status.no_service, alternatives=[]
            )

        return BoardItemResponse(
            **base,
            status=Status.ok,
            arrival=next_arrival,
            alternatives=alternatives,
        )

    def _handle_mbta_error(
        self,
        exc: MBTAError,
        stop: BoardItemConfig,
        now: datetime,
        base: dict,
    ) -> BoardItemResponse:
        """Handle MBTA errors: try stale cache, else return error."""
        stale = self._cache.get_stale(stop.key)
        if stale is not None:
            # Re-filter cached candidates against current time
            result = self._build_from_candidates(
                stale.value["candidates"],
                stale.value["source"],
                stop.walk_minutes,
                now,
                base,
            )
            if result.status == Status.ok:
                # Convert to stale status
                stored_at_utc = datetime.fromtimestamp(
                    stale.stored_at, tz=timezone.utc
                )
                return result.model_copy(
                    update={
                        "status": Status.stale,
                        "stale_as_of": stored_at_utc,
                    }
                )
            # All cached arrivals are past -> no_service
            return BoardItemResponse(
                **base, status=Status.no_service, alternatives=[]
            )

        # No cache at all -> error
        error_code = ErrorCode.mbta_unreachable
        if exc.status_code == 429:
            error_code = ErrorCode.mbta_rate_limited

        return BoardItemResponse(
            **base,
            status=Status.error,
            alternatives=[],
            error=ErrorDetail(
                code=error_code,
                message=str(exc),
            ),
        )
