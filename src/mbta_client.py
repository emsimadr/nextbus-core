"""
Async MBTA v3 API client.

Thin wrapper around httpx. Fetches predictions and schedules.
Raises MBTAError on failures.
"""

from __future__ import annotations

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class MBTAError(Exception):
    """Raised when an MBTA API call fails."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class MBTAClient:
    """Async client for the MBTA v3 API."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        base_url: str = "https://api-v3.mbta.com",
        api_key: Optional[str] = None,
    ) -> None:
        self._http = http_client
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        if self._api_key:
            return {"x-api-key": self._api_key}
        return {}

    async def fetch_predictions(
        self, route_id: str, stop_id: str, direction_id: int
    ) -> list[dict]:
        """
        Fetch realtime predictions from MBTA.

        Returns the `data` array from the MBTA response.
        Raises MBTAError on HTTP or connection failures.
        """
        params = {
            "filter[route]": route_id,
            "filter[stop]": stop_id,
            "filter[direction_id]": str(direction_id),
            "sort": "arrival_time",
            "page[limit]": "10",
        }
        return await self._fetch("/predictions", params)

    async def fetch_schedules(
        self, route_id: str, stop_id: str, direction_id: int
    ) -> list[dict]:
        """
        Fetch static schedule data from MBTA.

        Returns the `data` array from the MBTA response.
        Raises MBTAError on HTTP or connection failures.
        """
        params = {
            "filter[route]": route_id,
            "filter[stop]": stop_id,
            "filter[direction_id]": str(direction_id),
            "sort": "arrival_time",
            "page[limit]": "10",
        }
        return await self._fetch("/schedules", params)

    async def _fetch(self, path: str, params: dict) -> list[dict]:
        """Make an HTTP GET request to the MBTA API and return the data array."""
        url = f"{self._base_url}{path}"
        try:
            response = await self._http.get(
                url, params=params, headers=self._headers(), timeout=10.0
            )
        except httpx.HTTPError as exc:
            logger.error("MBTA request failed: %s %s -> %s", "GET", url, exc)
            raise MBTAError(f"Connection error: {exc}") from exc

        if response.status_code == 429:
            raise MBTAError("Rate limited by MBTA", status_code=429)

        if response.status_code != 200:
            raise MBTAError(
                f"MBTA returned {response.status_code}",
                status_code=response.status_code,
            )

        body = response.json()
        return body.get("data", [])
