# Changelog

All notable changes to the NextBus API will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-13

### Added

**API v1 - Initial Stable Release**

- Three endpoints:
  - `GET /v1/board` - All configured stops
  - `GET /v1/board/{key}` - Single stop by config key
  - `GET /health` - Health check (no auth)

- Response models:
  - `BoardResponse` - Collection of stops
  - `BoardItemResponse` - Single stop with arrival data
  - `Arrival` - Bus arrival with walk-time-aware leave time
  - `ErrorDetail` - Error information

- Status values:
  - `ok` - Fresh data from MBTA
  - `stale` - Serving cached data (MBTA unreachable)
  - `no_service` - No upcoming buses
  - `error` - Cannot serve data

- Source values:
  - `realtime` - MBTA predictions
  - `schedule` - MBTA schedule fallback

- Error codes:
  - `mbta_unreachable` - Upstream API failure
  - `mbta_rate_limited` - Rate limit exceeded
  - `unknown` - Unexpected error

- Features:
  - Walk-time aware `leave_in_minutes` computation
  - Realtime-first with schedule fallback
  - Stale mode for resilience (serves cached data up to 5 min)
  - Up to 2 alternative arrivals
  - Optional API key authentication via `X-API-Key` header
  - Caching (20s TTL) to avoid MBTA rate limits

- Documentation:
  - OpenAPI 3.0 specification (`api/openapi.json`)
  - JSON schemas for all response models (`api/schemas/`)
  - Example responses for all status combinations (`api/examples/`)
  - API contract and versioning policy (`api/CONTRACT.md`)
  - Client integration guide (`consumer-kit/README.md`)

### API Stability Guarantees

Within v1, the following are guaranteed stable:
- All endpoint paths
- All response field names and types
- All enum values
- HTTP status codes
- Authentication mechanism
- Timestamp format (ISO 8601 with timezone)

Non-breaking changes (new optional fields, new enum values) may be added without a version bump.

---

## Version History

| Version | Released   | Status    | Notes |
|---------|------------|-----------|-------|
| 1.0.0   | 2026-02-13 | ✅ Stable | Initial release |

## Migration Guides

No migrations yet. This is the first stable release.

When v2 is released (if needed), migration guides will appear here.
