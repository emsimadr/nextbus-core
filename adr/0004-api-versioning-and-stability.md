# ADR 0004: API Versioning and Stability Guarantees

**Status:** Accepted  
**Date:** 2026-02-13  
**Deciders:** Michael  
**Tags:** api, versioning, interoperability

## Context

The Bus Tracker API will be consumed by multiple client applications in separate repositories:
- ESP32 e-ink display (embedded C/C++)
- Home Assistant (Python REST sensor)
- Future TRMNL plugin
- Community-built clients

These clients need:
- **Stability guarantees** - Hard-coded field names won't break
- **Forward compatibility** - Clients should work with newer API versions that add fields
- **Clear deprecation** - Advance notice if breaking changes are needed
- **Machine-readable contract** - OpenAPI spec for code generation and validation

Embedded clients (ESP32) have special constraints:
- Limited memory for JSON parsing
- Hard-coded field names (cannot easily update firmware)
- Need to gracefully handle unknown enum values
- Cannot tolerate breaking changes without firmware updates

## Decision

### API Versioning Strategy

1. **URL-based major versioning**: `/v1/`, `/v2/`, etc.
   - Each major version is a separate path prefix
   - Multiple versions can coexist during migrations
   
2. **Semantic versioning within major version**:
   - Major (v1 → v2): Breaking changes (require new path)
   - Minor (1.0 → 1.1): Additive changes (new optional fields)
   - Patch (1.0.0 → 1.0.1): Bug fixes (no API changes)

3. **Stability guarantees within v1**:
   - ✅ Stable: Field names, types, enum values, endpoint paths, HTTP codes
   - ⚠️ Allowed: New optional fields, new enum values, new endpoints
   - 🚫 Breaking: Removing/renaming fields, changing types, removing enum values

### Contract Distribution

1. **OpenAPI 3.0 specification** at `api/openapi.json`
   - Auto-generated from FastAPI + Pydantic models
   - Committed to version control
   - Regenerated via `scripts/export_api_spec.py`

2. **JSON Schemas** at `api/schemas/*.json`
   - Individual schemas for each response model
   - Used for validation in tests
   - Available for client-side validation

3. **Example responses** at `api/examples/*.json`
   - Real-world examples for all status combinations
   - Used for offline development
   - Validated against JSON schemas

4. **Integration guide** in `consumer-kit/README.md`
   - ESP32/Arduino code examples
   - Error handling patterns
   - Polling strategies
   - Display recommendations

5. **Contract document** in `api/CONTRACT.md`
   - What will/won't break within v1
   - Deprecation policy (6 month minimum for old versions)
   - Consuming the API safely

### Deprecation Policy

If breaking changes are needed:
1. New major version path created (`/v2/`)
2. Old version maintained for **at least 6 months**
3. Deprecation announced in `CHANGELOG.md` with timeline
4. Both versions documented during transition

### Client Guidelines

For embedded/constrained clients:
- Hard-code `/v1/board/{key}` - guaranteed stable
- Parse only required fields, ignore unknown fields
- Handle all documented status values + default case
- Don't rely on specific error messages (may change)
- Validate `status` enum, fall back safely for unknown values

## Consequences

### Positive

- **Client confidence**: ESP32 firmware can hard-code field names safely
- **Forward compatibility**: Clients ignore new fields they don't need
- **Offline development**: Clients can develop against example JSON files
- **Contract testing**: Clients can validate responses against JSON schemas
- **Code generation**: OpenAPI enables SDK generation for any language
- **Documentation**: Interactive Swagger UI auto-generated from spec
- **Community adoption**: Clear contract lowers barrier for third-party clients

### Negative

- **Maintenance overhead**: Must regenerate OpenAPI spec after model changes
- **Breaking change cost**: Adding a major version requires maintaining two codebases
- **Coordination**: Changes require updating `CHANGELOG.md` and contract docs
- **Git churn**: Committing generated files (OpenAPI, schemas) increases repo size slightly

### Mitigation

- Automated script (`export_api_spec.py`) makes regeneration trivial
- Pydantic + FastAPI provide source-of-truth (models drive everything)
- Breaking changes are avoided by design (v1 is intentionally minimal)
- Git tracks diffs properly (JSON is diff-friendly)

## Alternatives Considered

### 1. No versioning, "latest" only

**Rejected:** Breaks embedded clients on every incompatible change. Firmware updates are expensive.

### 2. Header-based versioning (`Accept: application/vnd.bustracker.v1+json`)

**Rejected:** More complex for clients. URL-based versioning is simpler for curl, browsers, ESP32.

### 3. Keep OpenAPI spec only at runtime (not in repo)

**Rejected:** Clients need the spec before the service is running. Committing it enables offline development.

### 4. Semantic versioning in URLs (`/v1.0/`, `/v1.1/`)

**Rejected:** Only breaking changes need new paths. Minor/patch bumps don't affect URL.

## Notes

- The v1 API is intentionally minimal to avoid future breaking changes
- Pydantic models are the single source of truth
- FastAPI auto-generates accurate OpenAPI specs from Pydantic models
- Clients should be built defensively (ignore unknown fields, handle new enum values)
- The contract is more important than implementation details

## References

- [API Versioning Best Practices](https://restfulapi.net/versioning/)
- [OpenAPI 3.0 Specification](https://swagger.io/specification/)
- [Semantic Versioning](https://semver.org/)
- FastAPI OpenAPI documentation
- `spec/Service-API.md` - Original API spec
- `consumer-kit/README.md` - Client integration guide
