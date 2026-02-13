
# Deployment spec

## Target runtime

A small HTTP service that runs as a Docker container on the home network.

Primary: `docker compose up -d` on any machine (Raspberry Pi, NAS, old laptop, etc.)

## Community distribution

The Docker image is published to GitHub Container Registry. Setup for a new user:

1. Clone the repo (or just copy `docker-compose.yml`, `config.example.yaml`, and `.env.example`).
2. Copy `config.example.yaml` to `config.yaml` and edit with your stops.
3. Copy `.env.example` to `.env` and add your API keys.
4. Run `docker compose up -d`.

## Configuration

Secrets and non-secret config are separated by design.

### config.yaml (non-sensitive settings)

Mounted into the container at `/app/config.yaml`. See `config.example.yaml` for the full template.
Safe to share, paste in issues, or commit to a fork -- no secrets live here.

Fields:

- `cache_ttl`: seconds between MBTA refreshes (default 20)
- `stale_max_age`: seconds to serve stale data when MBTA is down (default 300)
- `stops`: list of BoardItemConfig objects (key, label, route_id, stop_id, direction_id, walk_minutes)

### .env (secrets and environment overrides)

Loaded by docker-compose via `env_file`. Gitignored -- never committed.

- `MBTA_API_KEY` -- MBTA v3 API key (strongly recommended; unauthenticated = 20 req/min limit)
- `API_KEY` -- optional; if set, all `/v1/*` requests require `X-API-Key` header
- `PORT` -- HTTP listen port (default `8080`)
- `LOG_LEVEL` -- logging level (default `info`)
- `CONFIG_PATH` -- path to config file (default `/app/config.yaml`)

### Why secrets are not in config.yaml

API keys must only live in `.env` (or environment variables). This prevents accidental exposure
when sharing config files for debugging or in community discussions. The config file is safe to
share; the `.env` file is not.

## Health check

`GET /health` returns `{"status": "healthy"}` with HTTP 200. Always unauthenticated.

Use in `docker-compose.yml`:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
  interval: 30s
  timeout: 5s
  retries: 3
```

## Observability

- Structured logs in JSON format.
- Log fields: request_id, route_id, stop_id, direction_id, status, cache_hit.
- No secrets in logs.
- Log level controlled by `LOG_LEVEL` env var.
