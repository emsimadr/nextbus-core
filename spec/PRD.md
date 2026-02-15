
# PRD: NextBus

## Problem

I want to know when to leave my house to catch the next bus. There are two nearby routes. One route has a terminal stop near home. Another route runs in two directions. The system must be configurable for which route, stop, and direction I care about.

## Users

- Primary: Michael at home, checking "when should I leave?" quickly
- Secondary: Home Assistant dashboards and automations
- Secondary: ESP32 e-ink display (dedicated mini screen in a 3D-printed case)
- Future: TRMNL e-ink dashboard plugin (one tile among many on the dashboard)
- Future: Community users in town who configure it for their own stops

## Goals

- Provide a single stable API that returns the next arrival with a realtime-first policy.
- Compute `leave_in_minutes` so clients know when to walk out the door, not just when the bus arrives.
- Keep embedded clients simple: one HTTP request, parse small JSON, display a number.
- Be safe to poll from Home Assistant and ESP32 without overloading MBTA.
- Be easy for community members to set up: edit a config file, run one Docker command.

## Non-goals (for now)

- Mapping, trip planning, multi-stop navigation, alerts, fare info
- Automatic nearby stop discovery via GPS
- User accounts or multi-tenant management
- Push notifications
- TRMNL plugin (future separate project that consumes this API)
- Personal prep time logic (handled by HA automations, not this service)

## Success criteria

- Correctness: arrival time and minutes align with MBTA prediction when available.
- Walk-time aware: `leave_in_minutes` correctly reflects walk time to stop.
- Latency: typical response under 250 ms from cache, under 1 s on cache miss.
- Resilience: returns a meaningful response even if MBTA errors (stale mode with re-filtering).
- Simplicity: one config file, one Docker command, two endpoints.

## Key constraints

- Realtime data is preferred. Schedule is fallback only.
- Configuration is via `config.yaml` with human-readable labels per stop.
- The API is versioned from day one (`/v1/...`).
- Docker is the primary distribution method for community sharing.
