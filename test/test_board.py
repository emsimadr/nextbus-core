"""Tests for board service (integration with mocked MBTA client)."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from src.board import BoardService
from src.cache import TTLCache
from src.config import AppConfig, BoardItemConfig
from src.mbta_client import MBTAClient, MBTAError
from src.models import ArrivalSource, Status


def _make_config(stops=None):
    if stops is None:
        stops = [
            BoardItemConfig(
                key="test_route",
                label="Test Route",
                route_id="77",
                stop_id="2261",
                direction_id=1,
                walk_minutes=4,
            )
        ]
    return AppConfig(
        mbta_api_key="fake",
        mbta_base_url="http://fake",
        cache_ttl=20,
        stale_max_age=300,
        stops=stops,
    )


def _future_time(minutes_from_now: int = 10) -> str:
    t = datetime.now(timezone.utc) + timedelta(minutes=minutes_from_now)
    return t.isoformat()


def _prediction(minutes_from_now=10, trip_id="trip-1"):
    return {
        "attributes": {
            "arrival_time": _future_time(minutes_from_now),
            "departure_time": None,
        },
        "relationships": {
            "trip": {"data": {"id": trip_id}},
            "route": {"data": {"id": "77"}},
            "stop": {"data": {"id": "2261"}},
        },
    }


class TestBoardService:
    def _make_service(self, config=None):
        config = config or _make_config()
        mbta = AsyncMock(spec=MBTAClient)
        cache = TTLCache(ttl=config.cache_ttl, stale_max_age=config.stale_max_age)
        service = BoardService(config=config, mbta_client=mbta, cache=cache)
        return service, mbta, cache

    @pytest.mark.asyncio
    async def test_realtime_happy_path(self):
        service, mbta, _ = self._make_service()
        mbta.fetch_predictions.return_value = [
            _prediction(minutes_from_now=8, trip_id="t1"),
            _prediction(minutes_from_now=20, trip_id="t2"),
        ]
        result = await service.get_board()
        assert len(result.items) == 1
        item = result.items[0]
        assert item.status == Status.ok
        assert item.arrival is not None
        assert item.arrival.source == ArrivalSource.realtime
        assert item.arrival.trip_id == "t1"
        assert item.arrival.minutes >= 7  # approximately 8
        assert item.arrival.leave_in_minutes == item.arrival.minutes - 4
        assert len(item.alternatives) == 1

    @pytest.mark.asyncio
    async def test_schedule_fallback(self):
        service, mbta, _ = self._make_service()
        mbta.fetch_predictions.return_value = []
        mbta.fetch_schedules.return_value = [
            _prediction(minutes_from_now=15, trip_id="sched-1"),
        ]
        result = await service.get_board()
        item = result.items[0]
        assert item.status == Status.ok
        assert item.arrival is not None
        assert item.arrival.source == ArrivalSource.schedule

    @pytest.mark.asyncio
    async def test_no_service(self):
        service, mbta, _ = self._make_service()
        mbta.fetch_predictions.return_value = []
        mbta.fetch_schedules.return_value = []
        result = await service.get_board()
        item = result.items[0]
        assert item.status == Status.no_service
        assert item.arrival is None
        assert item.alternatives == []

    @pytest.mark.asyncio
    async def test_stale_cache_on_error(self):
        service, mbta, cache = self._make_service()
        # First request succeeds (primes cache)
        mbta.fetch_predictions.return_value = [
            _prediction(minutes_from_now=30, trip_id="cached"),
        ]
        await service.get_board()

        # Second request: MBTA fails, cache still has data
        mbta.fetch_predictions.side_effect = MBTAError("down")
        # Expire fresh cache but keep stale
        cache._store["test_route"].stored_at -= 25  # past TTL
        result = await service.get_board()
        item = result.items[0]
        assert item.status == Status.stale
        assert item.arrival is not None
        assert item.stale_as_of is not None

    @pytest.mark.asyncio
    async def test_cold_start_error(self):
        service, mbta, _ = self._make_service()
        mbta.fetch_predictions.side_effect = MBTAError("down")
        result = await service.get_board()
        item = result.items[0]
        assert item.status == Status.error
        assert item.error is not None
        assert item.error.code.value == "mbta_unreachable"

    @pytest.mark.asyncio
    async def test_rate_limited_error(self):
        service, mbta, _ = self._make_service()
        mbta.fetch_predictions.side_effect = MBTAError("rate limited", status_code=429)
        result = await service.get_board()
        item = result.items[0]
        assert item.status == Status.error
        assert item.error.code.value == "mbta_rate_limited"

    @pytest.mark.asyncio
    async def test_get_board_item_by_key(self):
        service, mbta, _ = self._make_service()
        mbta.fetch_predictions.return_value = [
            _prediction(minutes_from_now=10),
        ]
        item = await service.get_board_item("test_route")
        assert item is not None
        assert item.key == "test_route"
        assert item.status == Status.ok

    @pytest.mark.asyncio
    async def test_get_board_item_not_found(self):
        service, mbta, _ = self._make_service()
        item = await service.get_board_item("nonexistent")
        assert item is None

    @pytest.mark.asyncio
    async def test_multiple_stops(self):
        config = _make_config(
            stops=[
                BoardItemConfig(
                    key="a", label="A", route_id="77", stop_id="2261",
                    direction_id=1, walk_minutes=4,
                ),
                BoardItemConfig(
                    key="b", label="B", route_id="350", stop_id="2281",
                    direction_id=1, walk_minutes=4,
                ),
            ]
        )
        service, mbta, _ = self._make_service(config=config)
        mbta.fetch_predictions.return_value = [_prediction(minutes_from_now=10)]
        result = await service.get_board()
        assert len(result.items) == 2
        assert result.items[0].key == "a"
        assert result.items[1].key == "b"

    @pytest.mark.asyncio
    async def test_cache_hit_skips_mbta_call(self):
        service, mbta, _ = self._make_service()
        mbta.fetch_predictions.return_value = [_prediction(minutes_from_now=15)]
        # First call primes cache
        await service.get_board()
        assert mbta.fetch_predictions.call_count == 1
        # Second call should hit cache
        await service.get_board()
        assert mbta.fetch_predictions.call_count == 1  # Not called again
