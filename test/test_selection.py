"""Tests for selection logic (pure functions, no I/O)."""

from datetime import datetime, timezone, timedelta

from src.models import ArrivalSource
from src.selection import resolve_timestamp, compute_minutes, select_arrivals


AS_OF = datetime(2026, 2, 13, 12, 34, 56, tzinfo=timezone.utc)


def _candidate(arrival_time=None, departure_time=None, trip_id="trip-1"):
    """Build a minimal MBTA candidate dict."""
    c = {
        "attributes": {
            "arrival_time": arrival_time,
            "departure_time": departure_time,
        },
        "relationships": {
            "trip": {"data": {"id": trip_id}},
        },
    }
    return c


class TestResolveTimestamp:
    def test_uses_arrival_time(self):
        c = _candidate(arrival_time="2026-02-13T12:41:00-05:00")
        ts = resolve_timestamp(c)
        assert ts is not None
        assert ts.minute == 41

    def test_falls_back_to_departure(self):
        c = _candidate(departure_time="2026-02-13T12:45:00-05:00")
        ts = resolve_timestamp(c)
        assert ts is not None
        assert ts.minute == 45

    def test_prefers_arrival_over_departure(self):
        c = _candidate(
            arrival_time="2026-02-13T12:41:00-05:00",
            departure_time="2026-02-13T12:42:00-05:00",
        )
        ts = resolve_timestamp(c)
        assert ts.minute == 41

    def test_returns_none_when_both_null(self):
        c = _candidate()
        assert resolve_timestamp(c) is None

    def test_returns_none_for_empty_attributes(self):
        assert resolve_timestamp({"attributes": {}}) is None


class TestComputeMinutes:
    def test_simple_minutes(self):
        arrival = AS_OF + timedelta(minutes=7)
        assert compute_minutes(arrival, AS_OF) == 7

    def test_floor_behavior(self):
        # 7 minutes and 45 seconds -> floor to 7
        arrival = AS_OF + timedelta(minutes=7, seconds=45)
        assert compute_minutes(arrival, AS_OF) == 7

    def test_zero_minutes(self):
        assert compute_minutes(AS_OF, AS_OF) == 0

    def test_negative_is_past(self):
        past = AS_OF - timedelta(minutes=3)
        assert compute_minutes(past, AS_OF) == -3


class TestSelectArrivals:
    def test_selects_earliest_future(self):
        candidates = [
            _candidate(arrival_time="2026-02-13T12:53:00Z", trip_id="trip-2"),
            _candidate(arrival_time="2026-02-13T12:41:00Z", trip_id="trip-1"),
        ]
        next_arr, alts = select_arrivals(candidates, AS_OF, walk_minutes=0, source=ArrivalSource.realtime)
        assert next_arr is not None
        assert next_arr.trip_id == "trip-1"
        assert next_arr.minutes == 6  # 12:41 - 12:34:56 = 6.06 -> floor 6
        assert len(alts) == 1
        assert alts[0].trip_id == "trip-2"

    def test_discards_past_arrivals(self):
        candidates = [
            _candidate(arrival_time="2026-02-13T12:30:00Z", trip_id="past"),
            _candidate(arrival_time="2026-02-13T12:50:00Z", trip_id="future"),
        ]
        next_arr, alts = select_arrivals(candidates, AS_OF, walk_minutes=0, source=ArrivalSource.realtime)
        assert next_arr is not None
        assert next_arr.trip_id == "future"
        assert len(alts) == 0

    def test_discards_null_timestamps(self):
        candidates = [
            _candidate(),  # both None
            _candidate(arrival_time="2026-02-13T12:50:00Z", trip_id="valid"),
        ]
        next_arr, alts = select_arrivals(candidates, AS_OF, walk_minutes=0, source=ArrivalSource.realtime)
        assert next_arr is not None
        assert next_arr.trip_id == "valid"

    def test_returns_none_when_all_past(self):
        candidates = [
            _candidate(arrival_time="2026-02-13T12:00:00Z"),
            _candidate(arrival_time="2026-02-13T12:10:00Z"),
        ]
        next_arr, alts = select_arrivals(candidates, AS_OF, walk_minutes=0, source=ArrivalSource.realtime)
        assert next_arr is None
        assert alts == []

    def test_returns_none_when_empty(self):
        next_arr, alts = select_arrivals([], AS_OF, walk_minutes=0, source=ArrivalSource.realtime)
        assert next_arr is None
        assert alts == []

    def test_alternatives_capped_at_2(self):
        candidates = [
            _candidate(arrival_time="2026-02-13T12:41:00Z", trip_id="t1"),
            _candidate(arrival_time="2026-02-13T12:50:00Z", trip_id="t2"),
            _candidate(arrival_time="2026-02-13T13:00:00Z", trip_id="t3"),
            _candidate(arrival_time="2026-02-13T13:10:00Z", trip_id="t4"),
        ]
        next_arr, alts = select_arrivals(candidates, AS_OF, walk_minutes=0, source=ArrivalSource.realtime)
        assert next_arr.trip_id == "t1"
        assert len(alts) == 2
        assert alts[0].trip_id == "t2"
        assert alts[1].trip_id == "t3"

    def test_leave_in_minutes_computed(self):
        candidates = [
            _candidate(arrival_time="2026-02-13T12:41:00Z"),
        ]
        next_arr, _ = select_arrivals(candidates, AS_OF, walk_minutes=4, source=ArrivalSource.realtime)
        assert next_arr is not None
        assert next_arr.minutes == 6
        assert next_arr.leave_in_minutes == 2  # 6 - 4

    def test_leave_in_minutes_can_be_negative(self):
        candidates = [
            _candidate(arrival_time="2026-02-13T12:37:00Z"),  # 2 min away
        ]
        next_arr, _ = select_arrivals(candidates, AS_OF, walk_minutes=5, source=ArrivalSource.realtime)
        assert next_arr is not None
        assert next_arr.minutes == 2
        assert next_arr.leave_in_minutes == -3  # 2 - 5

    def test_departure_time_fallback_in_selection(self):
        candidates = [
            _candidate(departure_time="2026-02-13T12:45:00Z", trip_id="dep-only"),
        ]
        next_arr, _ = select_arrivals(candidates, AS_OF, walk_minutes=0, source=ArrivalSource.realtime)
        assert next_arr is not None
        assert next_arr.trip_id == "dep-only"
        assert next_arr.minutes == 10

    def test_source_passed_through(self):
        candidates = [_candidate(arrival_time="2026-02-13T12:50:00Z")]
        next_arr, _ = select_arrivals(candidates, AS_OF, walk_minutes=0, source=ArrivalSource.schedule)
        assert next_arr.source == ArrivalSource.schedule

    def test_handles_timezone_aware_timestamps(self):
        # -05:00 timezone
        candidates = [
            _candidate(arrival_time="2026-02-13T07:41:00-05:00", trip_id="tz"),
        ]
        next_arr, _ = select_arrivals(candidates, AS_OF, walk_minutes=0, source=ArrivalSource.realtime)
        assert next_arr is not None
        assert next_arr.trip_id == "tz"
