"""
Pure selection logic for bus arrivals.

No I/O. Takes raw MBTA candidate dicts and returns Arrival model objects.
Implements spec/FunctionalSpec.md selection rules.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from src.models import Arrival, ArrivalSource


def resolve_timestamp(candidate: dict) -> Optional[datetime]:
    """
    Extract the best timestamp from an MBTA candidate.

    Uses arrival_time as primary, departure_time as fallback.
    Returns None if both are null/missing.
    """
    attrs = candidate.get("attributes", {})
    raw = attrs.get("arrival_time") or attrs.get("departure_time")
    if raw is None:
        return None
    return datetime.fromisoformat(raw)


def _extract_trip_id(candidate: dict) -> Optional[str]:
    """Extract trip ID from MBTA candidate relationships."""
    try:
        return candidate["relationships"]["trip"]["data"]["id"]
    except (KeyError, TypeError):
        return None


def compute_minutes(arrival_time: datetime, as_of: datetime) -> int:
    """
    Compute minutes until arrival.

    Returns floor of (arrival_time - as_of) in seconds / 60.
    """
    delta_seconds = (arrival_time - as_of).total_seconds()
    return math.floor(delta_seconds / 60)


def select_arrivals(
    candidates: list[dict],
    as_of: datetime,
    walk_minutes: int,
    source: ArrivalSource,
    max_alternatives: int = 2,
) -> tuple[Optional[Arrival], list[Arrival]]:
    """
    Filter, sort, and select arrivals from raw MBTA candidates.

    Args:
        candidates: Raw MBTA prediction or schedule data items.
        as_of: Reference timestamp (now).
        walk_minutes: Walk time to stop in minutes.
        source: Whether these are realtime predictions or schedule data.
        max_alternatives: Maximum number of alternative arrivals to include.

    Returns:
        Tuple of (next_arrival, alternatives). next_arrival is None if no
        future arrivals exist.
    """
    # 1. Resolve timestamps and filter
    resolved: list[tuple[datetime, dict]] = []
    for candidate in candidates:
        ts = resolve_timestamp(candidate)
        if ts is None:
            continue

        # Ensure timezone-aware comparison
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        minutes = compute_minutes(ts, as_of)
        if minutes < 0:
            continue  # In the past

        resolved.append((ts, candidate))

    # 2. Sort by timestamp ascending
    resolved.sort(key=lambda x: x[0])

    # 3. Build Arrival objects
    arrivals: list[Arrival] = []
    for ts, candidate in resolved:
        minutes = compute_minutes(ts, as_of)
        arrivals.append(
            Arrival(
                time=ts,
                minutes=minutes,
                leave_in_minutes=minutes - walk_minutes,
                source=source,
                trip_id=_extract_trip_id(candidate),
            )
        )

    if not arrivals:
        return None, []

    next_arrival = arrivals[0]
    alternatives = arrivals[1 : 1 + max_alternatives]
    return next_arrival, alternatives
