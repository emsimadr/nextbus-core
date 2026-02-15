
# MBTA v3 API usage contract

This project uses the MBTA v3 API.

**Official Documentation:**
- API Reference: https://api-v3.mbta.com/
- Best Practices: https://www.mbta.com/developers/v3-api/best-practices
- Real-Time Display Guidelines: https://www.mbta.com/developers/v3-api/best-practices#real-time-display-guidelines

## API key

**REQUIRED** for production use.

Rate limits:
- **Without API key:** 20 requests/min
- **With API key (free):** 1,000 requests/min

For a service polling 2+ routes every 20 seconds, an API key is effectively required.

Get a free key at: https://api-v3.mbta.com/

## Endpoints used

### Predictions: `GET /predictions`

Primary source (realtime data). Updates approximately every **12 seconds**.

Filters:
- `filter[stop]` = stop_id
- `filter[route]` = route_id
- `filter[direction_id]` = 0 or 1
- `page[limit]` = 10
- `sort` = arrival_time

### Schedules: `GET /schedules`

Fallback source (static timetable).

Same filters as predictions.

## MBTA Best Practices (Implemented)

### 1. Compression
**Status:** ✅ Recommended for implementation

Use `Accept-Encoding: gzip` header for ~10x data size reduction.

Example: Full route list reduces from 86 KB → 7.1 KB.

**Implementation:** httpx automatically handles gzip compression when the server supports it.

### 2. Sparse Fieldsets
**Status:** 📋 Recommended for future optimization

Use `fields[type]` parameter to request only needed attributes.

Example: `fields[prediction]=arrival_time,departure_time&fields[trip]=id`

**Benefits:**
- Reduces data transfer
- Lowers risk of rate limiting
- Faster response times

**Current:** We fetch all fields. Consider adding sparse fieldsets if rate limits become an issue.

### 3. HTTP Caching (If-Modified-Since)
**Status:** 📋 Recommended for future optimization

Use `Last-Modified` response and `If-Modified-Since` request headers.

**Benefits:**
- 304 Not Modified responses don't count toward rate limit
- Reduces bandwidth
- Prevents stale data from outdated servers

**Current:** We use application-level TTL caching. HTTP-level caching could be added as an enhancement.

### 4. Rate Limiting Strategy
**Status:** ✅ Implemented

- Use application caching (`cache_ttl`, default 20s) to avoid frequent MBTA calls
- Each board item results in at most 1 predictions call per cache TTL
- Schedule calls only happen when predictions yield no future arrivals
- With 3 configured stops and 20s cache TTL: worst case ~9 MBTA calls/min (well within 1,000/min limit)

## Timestamp resolution

Predictions and schedules may include `arrival_time`, `departure_time`, both, or neither.

**MBTA Rules** (per official documentation):
- **Departure time** is present if riders can **board** the vehicle at the stop
  - Null at the last stop on a trip (no departures)
- **Arrival time** is present if riders can **alight** from the vehicle at the stop
  - Null at the first stop on a trip (no arrivals)
- **Both null** indicates the vehicle will not make the scheduled stop
  - Check `schedule_relationship` field for explanation

**Our Resolution Order:**
1. Use `attributes.arrival_time` if present (primary)
2. Fall back to `attributes.departure_time` if arrival is null (fallback)
3. If both are null, discard the candidate

The resolved timestamp is returned as `time` in the API response. Clients never see the arrival/departure distinction -- the service handles it internally.

### Why We Prefer arrival_time

**The 30-60 Second Difference:**

At a normal stop:
```
12:05:30  arrival_time   ← Bus arrives, doors open
   |
   | [Passengers exit and enter]
   | [Typically 30-60 seconds]
   |
12:06:00  departure_time ← Doors close, bus leaves
```

**User Experience Impact:**

Using `departure_time` would be **risky**:
- User with 4-minute walk time would leave at 12:02:00
- User arrives at stop at 12:06:00 (exact departure time)
- **Risk:** Doors closing as user arrives, might miss bus

Using `arrival_time` is **safe**:
- User leaves at 12:01:30 (4 minutes before arrival)
- User arrives at stop at 12:05:30 (as bus arrives)
- **Benefit:** 30-60 second buffer to board comfortably

**Design Philosophy:**
- Conservative by design - better to arrive early than miss the bus
- Accessibility-friendly - users needing extra boarding time are covered
- Matches user mental model - "when will the bus **get there**?"

**Fallback Handling:**

The fallback to `departure_time` ensures correct behavior at edge cases:

| Stop Type | Fields Available | What We Use | Result |
|-----------|------------------|-------------|--------|
| **Normal stop** | Both present | `arrival_time` | ✅ Safe boarding buffer |
| **Origin (first stop)** | Only `departure_time` | `departure_time` | ✅ Shows when bus is sitting there |
| **Terminus (last stop)** | Only `arrival_time` | `arrival_time` | ✅ Shows when bus arrives |
| **Skipped stop** | Both null | Discarded | ✅ Correctly filtered out |

This 2-line fallback (`arrival_time or departure_time`) handles all MBTA stop types correctly without complex conditional logic.

## Fields consumed

**Predictions:**
- `data[].attributes.arrival_time` (ISO 8601 timestamp)
- `data[].attributes.departure_time` (ISO 8601 timestamp)
- `data[].attributes.status` (free-text boarding status, Commuter Rail)
- `data[].attributes.schedule_relationship` (enum: SCHEDULED, SKIPPED, NO_DATA, etc.)
- `data[].relationships.trip.data.id` (trip identifier)

**Schedules:**
- `data[].attributes.arrival_time` (ISO 8601 timestamp)
- `data[].attributes.departure_time` (ISO 8601 timestamp)

## Time format

All MBTA time values are ISO 8601 timestamps with timezone offset.

Format: `YYYY-MM-DDTHH:MM:SS±HH:MM`

Example: `2026-02-13T15:30:00-05:00` (3:30 PM EST)

## Update frequency

Per MBTA best practices:

- **Predictions:** Update approximately every **12 seconds**
- **Vehicles:** Update more than once per second
- **Our cache TTL:** 20 seconds (reasonable balance for predictions)

**Note:** Consider client-side smoothing to prevent relative times from bouncing between "3 minutes" and "4 minutes" if that would confuse users.

## Known gaps and future enhancements

### Alerts
**Status:** ❌ Not currently implemented

MBTA recommends showing relevant alerts to riders for service disruptions.

**Future implementation should:**
- Query alerts filtered by route and stops
- Show alerts for origin stops (BOARD activity)
- Show alerts for destination stops (EXIT activity)
- Show alerts for intermediate stops (RIDE activity)
- Filter by USING_WHEELCHAIR activity for accessible trips

**Reference:** https://www.mbta.com/developers/v3-api/best-practices#alerts

### Streaming
**Status:** ❌ Not currently needed

MBTA supports server-sent events for real-time data streaming instead of polling.

**Current:** Our polling model (20s cache TTL) is simpler and sufficient for current use case.

**Future:** Consider streaming if we need sub-second updates or have many consumers.

### Predictions status field
**Status:** ⚠️ Partially implemented

Predictions may have a `status` field (synonymous with `boarding_status` in GTFS Realtime).

**Current:** We don't expose this field to clients.

**Future:** Consider exposing for Commuter Rail predictions (e.g., "Boarding", "All Aboard", "Departed").

## Error handling

### HTTP Status Codes

- **200 OK:** Success, data in response body
- **304 Not Modified:** Cached data is still valid (with If-Modified-Since)
- **429 Too Many Requests:** Rate limit exceeded
  - Check `x-ratelimit-*` headers
  - Back off and retry
- **500 Server Error:** MBTA API issue
  - Serve stale cache if available
  - Return `error` status to clients if cache exhausted

### Rate Limit Headers

All responses include:
- `x-ratelimit-limit`: Maximum requests per time window
- `x-ratelimit-remaining`: Requests remaining in current window
- `x-ratelimit-reset`: UTC epoch seconds when limit resets

**Current:** We log these but don't actively monitor. Consider adding metrics.

## Service patterns and route variants

**Important:** Not all stops serve all routes in all directions at all times.

**Example:** Route 87 has multiple service patterns:
- Some stops only served during weekdays
- Some stops only served in one direction
- Route variants may skip certain stops

**Diagnosis:** If a stop shows `no_service`:
1. Verify `stop_id` exists on the route (query `/stops?filter[route]=<route_id>`)
2. Check both directions (0 and 1)
3. Check both predictions AND schedules
4. Consider time of day and day of week

**Tool:** Use the MBTA Trip Planner or route schedules on mbta.com to verify stop service.

## References

- [MBTA v3 API Documentation](https://api-v3.mbta.com/)
- [MBTA API Best Practices](https://www.mbta.com/developers/v3-api/best-practices)
- [Real-Time Display Guidelines](https://www.mbta.com/developers/v3-api/best-practices#real-time-display-guidelines)
- [MassDOT Developers License Agreement](https://www.mbta.com/developers/v3-api/best-practices) (governs use of MBTA data)
