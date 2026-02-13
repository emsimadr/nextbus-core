
# Home Assistant integration

Recommended approach: use Home Assistant REST sensor to poll `/v1/board/{key}`.

Home Assistant docs: https://www.home-assistant.io/integrations/sensor.rest/

## Single stop sensor

```yaml
sensor:
  - platform: rest
    name: "Bus Route 1"
    resource: "http://nextbus.local:8080/v1/board/route_1_inbound"
    value_template: >
      {{ value_json.arrival.leave_in_minutes
         if value_json.status in ['ok','stale']
         else 'unknown' }}
    unit_of_measurement: "min"
    json_attributes:
      - status
      - arrival
      - alternatives
      - label
      - walk_minutes
    scan_interval: 20
```

## Multiple stops (single request)

To avoid multiple HTTP calls, poll `/v1/board` once and extract values with template sensors:

```yaml
sensor:
  - platform: rest
    name: "Bus Board"
    resource: "http://nextbus.local:8080/v1/board"
    value_template: "{{ value_json.as_of }}"
    json_attributes:
      - items
    scan_interval: 20

template:
  - sensor:
      - name: "Route 1 Leave In"
        state: >
          {% set item = state_attr('sensor.bus_board', 'items')
             | selectattr('key', 'eq', 'route_1_inbound') | first %}
          {{ item.arrival.leave_in_minutes if item.status in ['ok','stale'] else 'unknown' }}
        unit_of_measurement: "min"
```

## Polling interval

- 20 seconds is recommended (matches the server-side cache TTL).
- The server caches upstream MBTA calls, so polling frequently is safe.

## Optional: API key authentication

If `API_KEY` is set in the bus-tracker `.env` file:

```yaml
sensor:
  - platform: rest
    name: "Bus Route 1"
    resource: "http://nextbus.local:8080/v1/board/route_1_inbound"
    headers:
      X-API-Key: "your-api-key-here"
    # ... rest of config
```
