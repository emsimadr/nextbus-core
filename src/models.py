"""
Pydantic response models for the bus-tracker API.

Direct translation of spec/DataModel.md.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ArrivalSource(str, Enum):
    realtime = "realtime"
    schedule = "schedule"


class Status(str, Enum):
    ok = "ok"
    no_service = "no_service"
    stale = "stale"
    error = "error"


class ErrorCode(str, Enum):
    mbta_unreachable = "mbta_unreachable"
    mbta_rate_limited = "mbta_rate_limited"
    unknown = "unknown"


class Arrival(BaseModel):
    """A single upcoming bus arrival."""

    time: datetime = Field(description="When the bus arrives at the stop (ISO 8601)")
    minutes: int = Field(ge=0, description="Minutes until bus arrives at stop")
    leave_in_minutes: int = Field(
        description="Minutes until you must leave the house (minutes - walk_minutes); can be negative"
    )
    source: ArrivalSource = Field(description="Whether this is realtime or schedule data")
    trip_id: Optional[str] = Field(default=None, description="MBTA trip ID for debugging")


class ErrorDetail(BaseModel):
    """Error information when status is 'error'."""

    code: ErrorCode
    message: str


class BoardItemResponse(BaseModel):
    """One configured stop with its next arrival."""

    key: str
    label: str
    route_id: str
    stop_id: str
    direction_id: int
    walk_minutes: int
    status: Status
    arrival: Optional[Arrival] = None
    alternatives: list[Arrival] = Field(default_factory=list)
    stale_as_of: Optional[datetime] = None
    error: Optional[ErrorDetail] = None


class BoardResponse(BaseModel):
    """Top-level response for GET /v1/board."""

    as_of: datetime
    items: list[BoardItemResponse]
