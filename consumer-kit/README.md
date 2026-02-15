# Consumer Kit

Everything you need to build an app that uses the Bus Tracker API.

## What's in This Folder

```
consumer-kit/
├── README.md              ← You are here
├── sample.cursorrules     ← Copy to your project as .cursorrules
└── examples/
    ├── ok_realtime.json   ← Success with realtime predictions
    ├── ok_schedule.json   ← Success with schedule fallback
    ├── stale.json         ← Serving cached data (MBTA down)
    ├── no_service.json    ← No buses found
    └── error.json         ← Error state
```

## How to Use

1. **Read this file** to understand the API
2. **Copy `sample.cursorrules`** to your project root as `.cursorrules` and fill in the placeholders
3. **Copy `examples/`** to your project for offline testing
4. **Build your app**

---

## What the API Does

The Bus Tracker API wraps the MBTA transit API and returns:

- **When to leave your house** (`leave_in_minutes`) accounting for walk time
- **When the bus arrives** (`minutes`)
- **Next few buses** (`alternatives`)
- **Data freshness** (`status`: realtime, cached, or unavailable)

---

## Endpoints

### `GET /v1/board/{key}` - Single Stop

Returns one configured stop. Recommended for most apps.

```http
GET /v1/board/route_1_inbound HTTP/1.1
Host: 192.168.1.100:8080
X-API-Key: your-api-key
```

### `GET /v1/board` - All Stops

Returns all configured stops. Use for multi-route dashboards.

### `GET /health` - Health Check

Returns `{"status": "healthy"}`. No auth required.

---

## Response Format

### Success (`status: "ok"`)

```json
{
  "key": "route_1_inbound",
  "label": "Route 1 - Harvard Sq",
  "route_id": "1",
  "stop_id": "place-harsq",
  "direction_id": 0,
  "walk_minutes": 4,
  "status": "ok",
  "arrival": {
    "time": "2026-02-13T12:41:00-05:00",
    "minutes": 6,
    "leave_in_minutes": 2,
    "source": "realtime",
    "trip_id": "trip-001"
  },
  "alternatives": [
    {
      "time": "2026-02-13T12:53:00-05:00",
      "minutes": 18,
      "leave_in_minutes": 14,
      "source": "realtime",
      "trip_id": "trip-002"
    }
  ]
}
```

**Meaning:** Bus arrives in 6 minutes. Leave in 2 minutes.

### Stale (`status: "stale"`)

Same shape as `ok`, but data is from cache because MBTA is unreachable. Includes `stale_as_of` timestamp.

### No Service (`status: "no_service"`)

```json
{
  "status": "no_service",
  "arrival": null,
  "alternatives": []
}
```

No upcoming buses (late night, holiday, etc.).

### Error (`status: "error"`)

```json
{
  "status": "error",
  "arrival": null,
  "alternatives": [],
  "error": {
    "code": "mbta_unreachable",
    "message": "Unable to reach MBTA API"
  }
}
```

API cannot serve any data. Error codes: `mbta_unreachable`, `mbta_rate_limited`, `unknown`.

---

## Field Reference

### Fields You'll Display

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `"ok"`, `"stale"`, `"no_service"`, `"error"` |
| `label` | string | Human-readable name, e.g. "Route 1 - Harvard Sq" |
| `arrival.leave_in_minutes` | int | When to leave the house. Can be negative. |
| `arrival.minutes` | int | When bus arrives at stop. Always ≥ 0. |
| `arrival.source` | string | `"realtime"` or `"schedule"` |

### Additional Fields

| Field | Type | Description |
|-------|------|-------------|
| `arrival.time` | string | ISO 8601 timestamp of arrival |
| `arrival.trip_id` | string or null | MBTA trip ID (debugging) |
| `alternatives` | array | Next 0-2 buses after the first |
| `stale_as_of` | string or null | When stale data was originally fetched |
| `error.code` | string | Error category |
| `error.message` | string | Human-readable error description |
| `key`, `route_id`, `stop_id`, `direction_id`, `walk_minutes` | various | Config metadata |

### Special Cases

- **`arrival` is null** when `status` is `no_service` or `error`
- **`leave_in_minutes` can be negative** - bus is coming but you can't walk there in time
- **`alternatives` may be empty** - normal, especially late at night
- **`source: "schedule"`** means no realtime prediction was available; the time comes from the static timetable

---

## Understanding Arrival Times

### What `arrival.time` Means

The API returns **when the bus arrives at the stop** (doors open), not when it departs (doors close).

```
12:05:30 ← Bus arrives (arrival.time) - doors open, you can board
   |
   |  [~30-60 seconds]
   |
12:06:00 ← Bus departs - doors close, bus leaves
```

**Why this matters:**

If the API said "12:06:00" (departure time), and you have a 4-minute walk:
- You'd leave at 12:02:00
- You'd arrive at 12:06:00 (exact departure time)
- **Result:** Doors closing as you arrive, might miss the bus ❌

With arrival time "12:05:30":
- You leave at 12:01:30
- You arrive at 12:05:30 (bus just arrived)
- **Result:** 30 seconds to board comfortably ✅

**The API is conservative by design** - it gives you time to board, not just barely make it.

### Edge Cases

The API handles these automatically:

| Scenario | What You Get | Why |
|----------|--------------|-----|
| **Normal stop** | Arrival time (doors open) | Gives you boarding buffer |
| **First stop (origin)** | Departure time (when bus is there) | Bus doesn't "arrive", it starts there |
| **Last stop (terminus)** | Arrival time | Bus arrives and stays |
| **Bus skipping stop** | Not included in results | Filtered out automatically |

**You don't need to handle these cases** - the API does it for you.

---

## Authentication

If the API has `API_KEY` configured, include:

```http
X-API-Key: your-key-here
```

If auth is not enabled, omit the header. The `/health` endpoint never requires auth.

---

## API Stability

**This is API version 1. These are guaranteed stable:**

- Endpoint paths (`/v1/board`, `/v1/board/{key}`, `/health`)
- Field names and types listed above
- Enum values: `ok`, `stale`, `no_service`, `error`, `realtime`, `schedule`
- HTTP status codes (200, 401, 404, 503)

**You can hard-code field names. They won't break.**

New optional fields or enum values may be added over time. Your parser should ignore fields it doesn't recognize.

If a breaking change is ever needed, it will be a new `/v2/` path. `/v1/` will continue working for at least 6 months.

---

## Integration Tips

### Polling

- **20-30 seconds** is the recommended interval (matches API cache TTL)
- Polling faster than 20s won't get fresher data
- Polling slower is fine for battery-constrained devices

### Error Handling

| HTTP Code | Meaning | Suggested Action |
|-----------|---------|------------------|
| 200 | Success | Parse response |
| 401 | Bad API key | Check configuration |
| 404 | Unknown stop key | Check stop key matches API config |
| 503 | Service starting | Retry after a few seconds |
| Network error | Can't reach API | Retry with backoff (1s, 2s, 4s, 8s) |

### Memory (Embedded Devices)

JSON response for a single stop is roughly 500-1500 bytes depending on alternatives.

- 1024-byte buffer: enough for status + arrival fields only
- 2048-byte buffer: comfortable for full response with alternatives

### Security

- Don't log or display API keys
- Don't commit API keys to version control
- Load keys from config files or environment variables

---

## Testing Offline

Copy the `examples/` folder into your project. Parse those files to verify your app handles all four statuses before connecting to the live API.

---

## More Resources (Optional)

These live in the `nextbus-core` repo if you need deeper detail:

- `api/CONTRACT.md` - Full versioning policy
- `api/openapi.json` - OpenAPI 3.0 spec (for code generation)
- `api/schemas/*.json` - JSON Schema for response validation
- http://localhost:8080/docs - Interactive Swagger UI (when API is running)
