
# Bus Tracker

A small API service that tells you when to leave your house to catch the next bus.
Wraps the MBTA v3 API with caching, fallback logic, and walk-time awareness.

## Consumers

- **Home Assistant** -- REST sensor for dashboards and automations
- **ESP32 e-ink display** -- dedicated mini screen in a 3D-printed case
- **TRMNL dashboard** -- future plugin for the TRMNL e-ink display
- **Browser / any HTTP client**

## Quick start

```bash
# 1. Copy and edit the config (stops, labels, walk times)
cp config.example.yaml config.yaml

# 2. Copy and edit secrets (API keys)
cp .env.example .env
# Edit .env with your MBTA API key

# 3. Run
docker compose up -d

# 4. Check
curl http://localhost:8080/v1/board
```

## API

| Endpoint              | Purpose                          |
| --------------------- | -------------------------------- |
| `GET /v1/board`       | All configured stops             |
| `GET /v1/board/{key}` | Single stop by config key        |
| `GET /health`         | Health check                     |

See `spec/Service-API.md` for the full contract.

## Configuration

- **`config.yaml`** -- your bus stops, labels, walk times, cache settings (safe to share)
- **`.env`** -- your API keys and secrets (never share or commit)

See `config.example.yaml` and `.env.example` for templates with comments.

## Development

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run tests (unit + integration + e2e)
pytest

# Run with coverage
pytest --cov=src --cov-report=term-missing

# Run smoke tests (requires real MBTA API key)
pytest -m smoke
```

## Project structure

```
spec/          Product and functional specs (source of truth)
adr/           Architecture decision records
plan/          Iteration plans and backlog
src/           Application source code
test/          Tests and fixtures
prompts/       Agent guardrails for Cursor
```

## Specs

Agents must treat `spec/` as the source of truth. Work in slices defined in `plan/Iteration-01.md`.
Any architecture changes require an ADR in `adr/`.
