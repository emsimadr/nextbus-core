# API Contract & Versioning Policy

This document defines the stability guarantees and versioning policy for the NextBus API. Consumer applications can rely on these rules when integrating with the service.

## Version: v1

Current version: **v1** (stable)

Base path: `/v1`

## Stability Guarantees

### What will NOT break within v1

✅ **Guaranteed stable** (safe to hard-code in clients):

- All endpoint paths (`/v1/board`, `/v1/board/{key}`, `/health`)
- All required fields in responses
- Field data types (string, int, datetime, enum values)
- HTTP status codes (200, 404, 401, 503)
- Authentication mechanism (X-API-Key header)
- Timestamp format (ISO 8601 with timezone)
- Enum values (`status`, `source`, `error.code`)

### What MAY change within v1 (non-breaking)

⚠️ **Additive changes allowed** (clients must ignore unknown fields):

- New optional fields in responses
- New enum values (clients should handle unknown values gracefully)
- New HTTP headers
- Additional error codes in `ErrorDetail.code`
- Additional endpoints (new paths under `/v1/`)

### What WILL break (requires v2)

🚫 **Breaking changes** (will trigger new API version):

- Removing or renaming existing fields
- Changing field types (e.g., `minutes` from int to float)
- Removing enum values that clients depend on
- Changing endpoint paths
- Changing authentication mechanism
- Removing endpoints

## OpenAPI Specification

Machine-readable API contract: `api/openapi.json`

Interactive docs (when service is running):
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`
- OpenAPI JSON: `http://localhost:8080/openapi.json`

## Deprecation Policy

If we need to introduce breaking changes:

1. A new version path will be created (`/v2/`)
2. The old version (`/v1/`) will be maintained for **at least 6 months**
3. Deprecation will be announced in `CHANGELOG.md` with a timeline
4. Both versions will be documented during the transition period

## Change Log

All API changes are documented in `CHANGELOG.md` with:
- Version bump (if applicable)
- Added/changed/deprecated/removed fields
- Migration guide for breaking changes

## Version History

| Version | Status | Released | Deprecated | Removed |
|---------|--------|----------|------------|---------|
| v1      | ✅ Stable | 2026-02 | - | - |
